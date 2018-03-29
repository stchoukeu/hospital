# -*- coding: utf-8 -*-

import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import osv, expression
from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare
from openerp.tools.misc import formatLang
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError, RedirectWarning, ValidationError
import openerp.addons.decimal_precision as dp
import logging


class HospitalActesmedicauxLine(models.Model):
    _name = 'hospital.actesmedicaux.line'
    _description = 'Medicals Acts Order Line'
    _order = 'actesmedicaux_id desc, sequence, id'
   
    @api.depends('state', 'product_uom_qty', 'qty_delivered', 'qty_to_invoice', 'qty_invoiced')
    def _compute_invoice_status(self):
        """
        Compute the invoice status of a SO line. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: we refer to the quantity to invoice of the line. Refer to method
          `_get_to_invoice_qty()` for more information on how this quantity is calculated.
        - upselling: this is possible only for a product invoiced on ordered quantities for which
          we delivered more than expected. The could arise if, for example, a project took more
          time than expected but we decided not to invoice the extra cost to the client. This
          occurs onyl in state 'sale', so that when a SO is set to done, the upselling opportunity
          is removed from the list.
        - invoiced: the quantity invoiced is larger or equal to the quantity ordered.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if line.state not in ('sale', 'done'):
                line.invoice_status = 'no'
            elif not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                line.invoice_status = 'to invoice'
            elif line.state == 'sale' and line.product_id.invoice_policy == 'order' and\
                    float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 1:
                line.invoice_status = 'upselling'
            elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                line.invoice_status = 'invoiced'
            else:
                line.invoice_status = 'no'

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.actesmedicaux_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.actesmedicaux_id.partner_id)
            line.update({
                'price_tax': taxes['total_included'] - taxes['total_excluded'],
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('product_id.invoice_policy', 'actesmedicaux_id.state')
    def _compute_qty_delivered_updateable(self):
        for line in self:
            line.qty_delivered_updateable = line.product_id.invoice_policy in ('order', 'delivery') and line.actesmedicaux_id.state == 'sale' and line.product_id.track_service == 'manual'

    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'actesmedicaux_id.state')
    def _get_to_invoice_qty(self):
        """
        Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
        calculated from the ordered quantity. Otherwise, the quantity delivered is used.
        """
        for line in self:
            if line.actesmedicaux_id.state in ['sale', 'done']:
                if line.product_id.invoice_policy == 'order':
                    line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                else:
                    line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
            else:
                line.qty_to_invoice = 0

    @api.depends('invoice_lines.invoice_id.state', 'invoice_lines.quantity')
    def _get_invoice_qty(self):
        """
        Compute the quantity invoiced. If case of a refund, the quantity invoiced is decreased. Note
        that this is the case only if the refund is generated from the SO and that is intentional: if
        a refund made would automatically decrease the invoiced quantity, then there is a risk of reinvoicing
        it automatically, which may not be wanted at all. That's why the refund has to be created from the SO
        """
        for line in self:
            qty_invoiced = 0.0
            for invoice_line in line.invoice_lines:
                if invoice_line.invoice_id.state != 'cancel':
                    if invoice_line.invoice_id.type == 'out_invoice':
                        qty_invoiced += self.env['product.uom']._compute_qty_obj(invoice_line.uom_id, invoice_line.quantity, line.product_uom)
                    elif invoice_line.invoice_id.type == 'out_refund':
                        qty_invoiced -= self.env['product.uom']._compute_qty_obj(invoice_line.uom_id, invoice_line.quantity, line.product_uom)
            line.qty_invoiced = qty_invoiced

    @api.depends('price_subtotal', 'product_uom_qty')
    def _get_price_reduce(self):
        for line in self:
            line.price_reduce = line.price_subtotal / line.product_uom_qty if line.product_uom_qty else 0.0

    @api.multi
    def _compute_tax_id(self):
        for line in self:
            fpos = line.actesmedicaux_id.fiscal_position_id or line.actesmedicaux_id.partner_id.property_account_position_id
            # If company_id is set, always filter taxes by the company
            taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(taxes) if fpos else taxes

    @api.multi
    def _prepare_order_line_procurement(self, group_id=False):
        self.ensure_one()
        return {
            'name': self.name,
            'origin': self.actesmedicaux_id.name,
            'date_planned': datetime.strptime(self.actesmedicaux_id.date_order, DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(days=self.customer_lead),
            'product_id': self.product_id.id,
            'product_qty': self.product_uom_qty,
            'product_uom': self.product_uom.id,
            'company_id': self.actesmedicaux_id.company_id.id,
            'group_id': group_id,
            'sale_line_id': self.id
        }

    @api.multi
    def _action_procurement_create(self):
        """
        Create procurements based on quantity ordered. If the quantity is increased, new
        procurements are created. If the quantity is decreased, no automated action is taken.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        new_procs = self.env['procurement.order'] #Empty recordset
        for line in self:
            if line.state != 'sale' or not line.product_id._need_procurement():
                continue
            qty = 0.0
            for proc in line.procurement_ids:
                qty += proc.product_qty
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            if not line.actesmedicaux_id.procurement_group_id:
                vals = line.actesmedicaux_id._prepare_procurement_group()
                line.actesmedicaux_id.procurement_group_id = self.env["procurement.group"].create(vals)

            vals = line._prepare_order_line_procurement(group_id=line.actesmedicaux_id.procurement_group_id.id)
            vals['product_qty'] = line.product_uom_qty - qty
            new_proc = self.env["procurement.order"].with_context(procurement_autorun_defer=True).create(vals)
            new_procs += new_proc
        new_procs.run()
        return new_procs

    @api.model
    def _get_analytic_invoice_policy(self):
        return ['cost']

    @api.model
    def _get_analytic_track_service(self):
        return []

    @api.model
    def _get_purchase_price(self, pricelist, product, product_uom, date):
        return {}

    @api.model
    def create(self, values):
        onchange_fields = ['name', 'price_unit', 'product_uom', 'tax_id']
        if values.get('actesmedicaux_id') and values.get('product_id') and any(f not in values for f in onchange_fields):
            line = self.new(values)
            line.product_id_change()
            for field in onchange_fields:
                if field not in values:
                    values[field] = line._fields[field].convert_to_write(line[field])
        line = super(HospitalActesmedicauxLine, self).create(values)
        if line.state == 'sale':
            if (not line.actesmedicaux_id.project_id and
                (line.product_id.track_service in self._get_analytic_track_service() or
                 line.product_id.invoice_policy in self._get_analytic_invoice_policy())):
                line.actesmedicaux_id._create_analytic_account()
            line._action_procurement_create()

        return line

    @api.multi
    def write(self, values):
        lines = False
        if 'product_uom_qty' in values:
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            lines = self.filtered(
                lambda r: r.state == 'sale' and float_compare(r.product_uom_qty, values['product_uom_qty'], precision_digits=precision) == -1)
        result = super(HospitalActesmedicauxLine, self).write(values)
        if lines:
            lines._action_procurement_create()
        return result

   
    actesmedicaux_id = fields.Many2one(
        comodel_name='hospital.actesmedicaux',
        string='Hospital Medical Acts',
        required=False,
        index=True,
        ondelete='cascade',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Hospital Medical Acts.',
        copy=False
    ) 
    
    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    invoice_lines = fields.Many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id', 'invoice_line_id', string='Invoice Lines', copy=False)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', compute='_compute_invoice_status', store=True, readonly=True, default='no')
    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    price_tax = fields.Monetary(compute='_compute_amount', string='Taxes', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)

    price_reduce = fields.Monetary(compute='_get_price_reduce', string='Price Reduce', readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes', domain=['|', ('active', '=', False), ('active', '=', True)])

    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)

    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)], change_default=True, ondelete='restrict', required=True)
    product_uom_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)
    product_uom = fields.Many2one('product.uom', string='Unit of Measure', required=True)

    qty_delivered_updateable = fields.Boolean(compute='_compute_qty_delivered_updateable', string='Can Edit Delivered', readonly=True, default=True)
    qty_delivered = fields.Float(string='Delivered', copy=False, digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    qty_to_invoice = fields.Float(
        compute='_get_to_invoice_qty', string='To Invoice', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'), default=0.0)
    qty_invoiced = fields.Float(
        compute='_get_invoice_qty', string='Invoiced', store=True, readonly=True,
        digits=dp.get_precision('Product Unit of Measure'), default=0.0)

    salesman_id = fields.Many2one(related='actesmedicaux_id.user_id', store=True, string='Salesperson', readonly=True)
    currency_id = fields.Many2one(related='actesmedicaux_id.currency_id', store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='actesmedicaux_id.company_id', string='Company', store=True, readonly=True)
    order_partner_id = fields.Many2one(related='actesmedicaux_id.partner_id', store=True, string='Customer')

    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sale Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], related='actesmedicaux_id.state', string='Order Status', readonly=True, copy=False, store=True, default='draft')

    customer_lead = fields.Float(
        'Delivery Lead Time', required=True, default=0.0,
        help="Number of days between the order confirmation and the shipping of the products to the customer", oldname="delay")
    procurement_ids = fields.One2many('procurement.order', 'sale_line_id', string='Procurements')

    _sql_constraints = [
            ('product_and_actemedicaux_uniq', 'unique (actesmedicaux_id,product_id)', "Le produit est déja dans la liste!"),
    ]
    @api.multi
    def _prepare_invoice_line(self, qty):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        res = {}
        account = self.product_id.property_account_income_id or self.product_id.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                            (self.product_id.name, self.product_id.id, self.product_id.categ_id.name))

        fpos = self.actesmedicaux_id.fiscal_position_id or self.actesmedicaux_id.partner_id.property_account_position_id
        if fpos:
            account = fpos.map_account(account)

        res = {
            'name': self.name,
            'sequence': self.sequence,
            'origin': self.actesmedicaux_id.name,
            'account_id': account.id,
            'price_unit': self.price_unit,
            'quantity': qty,
            'discount': self.discount,
            'uom_id': self.product_uom.id,
            'product_id': self.product_id.id or False,
            'invoice_line_tax_ids': [(6, 0, self.tax_id.ids)],
            'account_analytic_id': self.actesmedicaux_id.project_id.id,
        }
        return res

    @api.multi
    def invoice_line_create(self, invoice_id, qty):
        """
        Create an invoice line. The quantity to invoice can be positive (invoice) or negative
        (refund).

        :param invoice_id: integer
        :param qty: float quantity to invoice
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not float_is_zero(qty, precision_digits=precision):
                vals = line._prepare_invoice_line(qty=qty)
                vals.update({'invoice_id': invoice_id, 'sale_line_ids': [(6, 0, [line.id])]})
                self.env['account.invoice.line'].create(vals)

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}

        vals = {}
        domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
            vals['product_uom_qty'] = 1.0

        product = self.product_id.with_context(
            lang=self.actesmedicaux_id.partner_id.lang,
            partner=self.actesmedicaux_id.partner_id.id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.actesmedicaux_id.date_order,
            pricelist=self.actesmedicaux_id.pricelist_id.id,
            uom=self.product_uom.id
        )

        name = product.name_get()[0][1]
        if product.description_sale:
            name += '\n' + product.description_sale
        vals['name'] = name

        self._compute_tax_id()

        if self.actesmedicaux_id.pricelist_id and self.actesmedicaux_id.partner_id:
            vals['price_unit'] = self.env['account.tax']._fix_tax_included_price(product.price, product.taxes_id, self.tax_id)
        self.update(vals)
        return {'domain': domain}

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom:
            self.price_unit = 0.0
            return
        if self.actesmedicaux_id.pricelist_id and self.actesmedicaux_id.partner_id:
            product = self.product_id.with_context(
                lang=self.actesmedicaux_id.partner_id.lang,
                partner=self.actesmedicaux_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.actesmedicaux_id.date_order,
                pricelist=self.actesmedicaux_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            self.price_unit = self.env['account.tax']._fix_tax_included_price(product.price, product.taxes_id, self.tax_id)

    @api.multi
    def unlink(self):
        if self.filtered(lambda x: x.state in ('sale', 'done')):
            raise UserError(_('You can not remove a sale order line.\nDiscard changes and try setting the quantity to 0.'))
        return super(HospitalActesmedicauxLine, self).unlink()

    @api.multi
    def _get_delivered_qty(self):
        '''
        Intended to be overridden in sale_stock and sale_mrp
        :return: the quantity delivered
        :rtype: float
        '''
        return 0.0
    
class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.multi
    def send_mail(self, auto_commit=False):
        if self._context.get('default_model') == 'sale.order' and self._context.get('default_res_id') and self._context.get('mark_so_as_sent'):
            order = self.env['sale.order'].browse([self._context['default_res_id']])
            if order.state == 'draft':
                order.state = 'sent'
            self = self.with_context(mail_post_autofollow=True)
            
        if self._context.get('default_model') == 'hospital.actesmedicaux' and self._context.get('default_res_id') and self._context.get('mark_so_as_sent'):
            order = self.env['hospital.actesmedicaux'].browse([self._context['default_res_id']])
            #if order.state == 'draft':
            #    order.state = 'sent'
            self = self.with_context(mail_post_autofollow=True)
            
        return super(MailComposeMessage, self).send_mail(auto_commit=auto_commit)
