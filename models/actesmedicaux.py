# -*- coding: utf-8 -*-
import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import osv, expression
from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare,float_round
from openerp.tools.misc import formatLang
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT

from openerp.exceptions import UserError, RedirectWarning, ValidationError



class HospitalactesMedicaux(models.Model):
     _name = 'hospital.actesmedicaux' 
     _inherit = ['mail.thread', 'ir.needaction_mixin']
     #_inherit = ['sale.order']
     _description = "Sale Medical Act"
     _order = 'date_order desc, id desc'

     @api.depends('actesmedicaux_lines.price_total')
     def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.actesmedicaux_lines:
                amount_untaxed += line.price_subtotal
                # FORWARDPORT UP TO 10.0
                if order.company_id.tax_calculation_rounding_method == 'round_globally':
                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                    taxes = line.tax_id.compute_all(price, line.actesmedicaux_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.actesmedicaux_id.partner_id)
                    amount_tax += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                else:
                    amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.pricelist_id.currency_id.round(amount_untaxed),
                'amount_tax': order.pricelist_id.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

     @api.depends('state', 'actesmedicaux_lines.invoice_status')
     def _get_invoiced(self):
        """
        Compute the invoice status of a SO. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: if any SO line is 'to invoice', the whole SO is 'to invoice'
        - invoiced: if all SO lines are invoiced, the SO is invoiced.
        - upselling: if all SO lines are invoiced or upselling, the status is upselling.

        The invoice_ids are obtained thanks to the invoice lines of the SO lines, and we also search
        for possible refunds created directly from existing invoices. This is necessary since such a
        refund is not directly linked to the SO.
        """
        for order in self:
            invoice_ids = order.actesmedicaux_lines.mapped('invoice_lines').mapped('invoice_id').filtered(lambda r: r.type in ['out_invoice', 'out_refund'])
            # Search for invoices which have been 'cancelled' (filter_refund = 'modify' in
            # 'account.invoice.refund')
            # use like as origin may contains multiple references (e.g. 'SO01, SO02')
            refunds = invoice_ids.search([('origin', 'like', order.name)]).filtered(lambda r: r.type in ['out_invoice', 'out_refund'])
            invoice_ids |= refunds.filtered(lambda r: order.name in [origin.strip() for origin in r.origin.split(',')])
            # Search for refunds as well
            refund_ids = self.env['account.invoice'].browse()
            if invoice_ids:
                for inv in invoice_ids:
                    refund_ids += refund_ids.search([('type', '=', 'out_refund'), ('origin', '=', inv.number), ('origin', '!=', False), ('journal_id', '=', inv.journal_id.id)])

            line_invoice_status = [line.invoice_status for line in order.actesmedicaux_lines]

            if order.state not in ('sale', 'done'):
                invoice_status = 'no'
            elif any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
                invoice_status = 'to invoice'
            elif all(invoice_status == 'invoiced' for invoice_status in line_invoice_status):
                invoice_status = 'invoiced'
            elif all(invoice_status in ['invoiced', 'upselling'] for invoice_status in line_invoice_status):
                invoice_status = 'upselling'
            else:
                invoice_status = 'no'

            order.update({
                'invoice_count': len(set(invoice_ids.ids + refund_ids.ids)),
                'invoice_ids': invoice_ids.ids + refund_ids.ids,
                'invoice_status': invoice_status
            })

     @api.model
     def _default_note(self):
        return self.env.user.company_id.sale_note

     @api.model
     def _get_default_team(self):
        default_team_id = self.env['crm.team']._get_default_team_id()
        return self.env['crm.team'].browse(default_team_id)

     @api.onchange('fiscal_position_id')
     def _compute_tax_id(self):
        """
        Trigger the recompute of the taxes if the fiscal position is changed on the SO.
        """
        for order in self:
            order.actesmedicaux_lines._compute_tax_id()                    

 
     name = fields.Char(
        #compute='_compute_name',
        store= True,
        #inverse='_inverse_name',
     ) 
     state = fields.Selection([
            ('draft','Draft'),
            ('cancel', 'Cancel'),
            ('confirm', 'Confirm'),
            ('paid', 'Paid'),
            ('delivered', 'Delivered'),
        ], string='Status', index=True, readonly=True, default='draft', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed record.\n"
             " * The 'Cancel' status is used when a user cancel the record.\n"
             " * The 'Confirm' status is used when user create the medical acte and the medical act is not yet paid.\n"
             " * The 'Paid' status is set automatically when the invoice related to the number of this medical act is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Delivered' status is used when the bill of the patient is Allrady paid.\n")

     patient_id = fields.Many2one(
        string='Patient',
        comodel_name='medical.patient',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Patient that is(will) consulted.',
     )
     physician_id = fields.Many2one(
        string='Physician',
        comodel_name='medical.physician',
        readonly=True,
        required=True,
        states={'draft': [('readonly', False)]},
        help='Physician who is(will) consult the patient',
     ) 

     actesmedicaux_lines = fields.One2many(
        comodel_name='hospital.actesmedicaux.line', 
        inverse_name='actesmedicaux_id', 
        string='Order Lines', 
        states={'cancel': [('readonly', True)], 
                'done': [('readonly', True)],
                'confirm': [('readonly', True)],
                'paid': [('readonly', True)],
                'delivered': [('readonly', True)]
               },
        copy=True
     )
      
     invoice_id = fields.Many2one(
        string='Patient Invoice',
        comodel_name='account.invoice',
        required=False,
        index=True,
        readonly=True,
        help='The invoice linked with this Consultation',
     )
     invoice_state = fields.Selection(
        string='Patient Invoice state', 
        store=False, 
        readonly=False,
        related='invoice_id.state',
     )
     supplier_invoice_id = fields.Many2one(
        string='Physician Invoice',
        comodel_name='account.invoice',
        required=False,
        index=True,
        readonly=True,
        help='The invoice of the external physician',
     )
     supplier_invoice_state = fields.Selection(
        string='Physician Invoice state', 
        store=False, 
        readonly=False,
        related='supplier_invoice_id.state',
     )
     observation = fields.Text(
        string='Observation', 
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Why the patient is/was Hospitalized',
     )

     origin = fields.Char(string='Source Document', help="Reference of the document that generated this sales order request.")
     client_order_ref = fields.Char(string='Customer Reference', copy=False)
     date_order = fields.Datetime(string='Order Date', required=True, readonly=True, index=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False, default=fields.Datetime.now)
     validity_date = fields.Date(string='Expiration Date', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
     create_date = fields.Datetime(string='Creation Date', readonly=True, index=True, help="Date on which sales order is created.")

     user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange', default=lambda self: self.env.user)
     partner_id = fields.Many2one('res.partner', string='Customer', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, required=True, change_default=True, index=True, track_visibility='always')
     partner_invoice_id = fields.Many2one('res.partner', string='Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="Invoice address for current sales order.")
     partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="Delivery address for current sales order.")

     pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="Pricelist for current sales order.")
     currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True, required=True)
     project_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="The analytic account related to a sales order.", copy=False, domain=[('account_type', '=', 'normal')])


     invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoiced', readonly=True)
     invoice_ids = fields.Many2many("account.invoice", string='Invoices', compute="_get_invoiced", readonly=True, copy=False)
     invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True, default='no')

     note = fields.Text('Terms and conditions', default=_default_note)

     amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all', track_visibility='always')
     amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all', track_visibility='always')
     amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', track_visibility='always')

     payment_term_id = fields.Many2one('account.payment.term', string='Payment Term', oldname='payment_term')
     fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position', string='Fiscal Position')
     company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('sale.order'))
     team_id = fields.Many2one('crm.team', 'Sales Team', change_default=True, default=_get_default_team, oldname='section_id')
     procurement_group_id = fields.Many2one('procurement.group', 'Procurement Group', copy=False)

     product_id = fields.Many2one('product.product', related='actesmedicaux_lines.product_id', string='Product')
   
    
     @api.multi
     @api.onchange('patient_id')
     def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Pricelist
        - Payment term
        - Invoice address
        - Delivery address
        """
        if not self.patient_id:
            self.update({
                'partner_id': False,
                'partner_invoice_id': False,
                'partner_shipping_id': False,
                'payment_term_id': False,
                'fiscal_position_id': False,
            })
            return

        addr = self.patient_id.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'pricelist_id': self.patient_id.partner_id.property_product_pricelist and self.patient_id.partner_id.property_product_pricelist.id or False,
            'payment_term_id': self.patient_id.partner_id.property_payment_term_id and self.patient_id.partner_id.property_payment_term_id.id or False,
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
        }
        values['partner_id'] = self.patient_id.partner_id.id,
        
        if self.env.user.company_id.sale_note:
            values['note'] = self.with_context(lang=self.patient_id.partner_id.lang).env.user.company_id.sale_note

        if self.patient_id.partner_id.user_id:
            values['user_id'] = self.patient_id.partner_id.user_id.id
        if self.partner_id.team_id:
            values['team_id'] = self.patient_id.partner_id.team_id.id
        self.update(values)

     @api.multi
     def unlink(self):
        for actemedicaux in self:
            if actemedicaux.state != 'draft' and actemedicaux.state!='cancel' and actemedicaux.supplier_invoice_id:
                raise UserError(_('You can only delete draft  or cancel  medical Acts!'))
                #raise osv.except_osv(_('Attention!!'),_('You can only delete draft or cancel record'))
                #raise Warning(_('You can only delete draft or cancel record'))
        return super(HospitalactesMedicaux, self).unlink()

     @api.model
     def create(self, vals):
        vals['state'] = 'draft'
        if vals.get('name', _('New')) == _('New'):
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('sale.order') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order') or _('New')

        # Makes sure partner_invoice_id', 'partner_shipping_id' and 'pricelist_id' are defined
        if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id']):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            addr = partner.address_get(['delivery', 'invoice'])
            vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
            vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
            vals['pricelist_id'] = vals.setdefault('pricelist_id', partner.property_product_pricelist and partner.property_product_pricelist.id)
        result = super(HospitalactesMedicaux, self.with_context(mail_create_nolog=True)).create(vals)
        return result

     @api.multi 
     def write(self,values):
     #   for actesmedicaux in self:
     #       old_state=actesmedicaux.state 
     #       new_state=values['state']
     #       changes = []
     #       changes.append(_("State change from '%s' to '%s'") %(old_state,new_state))
     #       self.message_post(body=", state change to ".join(changes))
        result= super(HospitalactesMedicaux, self.with_context(mail_create_nolog=True)).write(values)
        return result   
                
     @api.multi
     def name_get(self):
        result = []
        for actesmedicaux in self:
            if not actesmedicaux.invoice_id:
                #name = "[{}] {}".format(record.id, record.name)
                name = "[%s] %s" % (actesmedicaux.create_date, actesmedicaux.physician_id.name)
                result.append((actesmedicaux.id,name) )
        return result
    
     @api.multi
     @api.depends('patient_id', 'physician_id', 'invoice_id')
     def _compute_name(self):
        for actesmedicaux in self:
            name = actesmedicaux.product_id.name
            if actesmedicaux.invoice_id:
                name = 'INV %s : %s' % (actesmedicaux.invoice_id.id,name)
            else:
                name = '%s : %s' % (actesmedicaux.create_date,name)
            actesmedicaux.name = name   
   
     @api.multi
     def bouton_delivered(self):
        for actesmedicaux in self:
            invoice=actesmedicaux.invoice_id
            if not invoice or invoice.state!='paid':
                raise osv.except_osv(_('No paiement detected!!'),_('Please know that the attached bill is not paid. Please perform paiement of the bill first')) 
             
            actesmedicaux.write({'state': 'delivered'})
                                                           
     @api.multi
     def bouton_paid(self):
        for actesmedicaux in self:
            invoice=actesmedicaux.invoice_id
            if not invoice or invoice.state!='paid':
                raise osv.except_osv(_('No paiement detected!!'),_('Please know that the attached bill is not paid. Please perform paiement of the bill first')) 
                #invoice.confirm_paid()
            actesmedicaux.supplier_invoice_id.invoice_validate()
            actesmedicaux.write({'state': 'paid'})

     @api.multi
     def bouton_cancel(self):
        for actesmedicaux in self:
            actesmedicaux.write({'state': 'cancel'})
                
     @api.multi
     def bouton_confirm(self):
                #preparing invoice
        
        for actesmedicaux in self:
            
            if not actesmedicaux.actesmedicaux_lines:
                raise UserError(_('There is no medical acts line.'))
            if actesmedicaux.actesmedicaux_lines:
                self.ensure_one()
                journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
                if not journal_id:
                    raise osv.except_osv(_('Attention!!'),_('Please define an accounting sale journal for this company.'))
                                    
                invoice_vals = {
                    'name': actesmedicaux.patient_id.partner_id.name,
                    'actesmedicaux_id': actesmedicaux.id,
                    'physician_id': actesmedicaux.physician_id.id,
                    'origin':  'Hospitalization -> #%s' % (actesmedicaux.id),
                    'type': 'out_invoice',
                    'account_id': actesmedicaux.patient_id.partner_id.property_account_receivable_id.id,
                    'partner_id': actesmedicaux.patient_id.partner_id.id,
                    'journal_id': journal_id,
                    'currency_id': actesmedicaux.product_id.currency_id.id,
                    'comment': '------------- ',
                    'payment_term_id': actesmedicaux.patient_id.partner_id.property_payment_term_id.id,
                    'fiscal_position_id': actesmedicaux.patient_id.partner_id.property_account_position_id.id ,
                    'company_id': actesmedicaux.patient_id.partner_id.company_id.id,
                    'user_id': actesmedicaux.create_uid.id,
                    'team_id': actesmedicaux.create_uid.team_id.id
                }
               
                invoice=self.env['account.invoice'].create(invoice_vals)
                
                for line in actesmedicaux.actesmedicaux_lines:   
                    if not line.product_id.property_account_income_id and not line.product_id.categ_id.property_account_income_categ_id:
                        raise osv.except_osv(_('Attention!!'),_('Please specify the revenue account in the accounting tab of this Medical act or product(service).'))  
                    #actesmedicaux.write({'end_date':fields.Date.context_today(self)}) 
                   
                    #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
                    #invoice= self.env['account.invoice'].browse(invoice.id) 
                    precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
                    if float_is_zero(line.product_uom_qty, precision_digits=precision):
                        continue
                    property_account_income_id=False
                    if line.product_id.property_account_income_id:
                        property_account_income_id= line.product_id.property_account_income_id.id
                    else:
                        property_account_income_id= line.product_id.categ_id.property_account_income_categ_id.id
                    
                    invoice_line_vals = { 
                        'name': line.product_id.name,
                        'origin': 'INV: %s => %s' % (invoice.id,actesmedicaux.patient_id.partner_id.name),
                        'sequence': 1,
                        'invoice_id': invoice.id,
                        'uom_id': line.product_id.uom_id.id,
                        'product_id': line.product_id.id,
                        'account_id': property_account_income_id,
                        'price_unit': line.price_unit, #Envisager d'appeler plutot la fonction qui renvoie le prix de la liste des prix (self.lit_id.categorie_id.product_id.list_price,) 
                        'price_subtotal': line.price_subtotal,
                        'price_subtotal_signed': line.price_subtotal,
                        'quantity': line.product_uom_qty,
                        'discount': 0,
                        'company_id': actesmedicaux.patient_id.partner_id.company_id.id,
                        'partner_id': actesmedicaux.patient_id.partner_id.id,
                        'currency_id': line.product_id.currency_id.id,
                        'company_currency_id': line.product_id.currency_id.id,
                        #'invoice_line_tax_ids':
                        'account_analytic_id': False
                    } 
                    invoice_line=self.env['account.invoice.line'].create(invoice_line_vals)
                    #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
                    #invoice_line= self.env['account.invoice.line'].browse(ids_invoice_line[0])
                    invoice_line._set_taxes();
                    invoice_line._compute_price();
                    self.env['account.invoice.line'].write(invoice_line)
                            
                invoice._onchange_invoice_line_ids();
                invoice._compute_amount();
                vals = { 
                        'tax_line_ids': invoice.tax_line_ids,
                        'amount_untaxed': invoice.amount_untaxed,
                        'amount_tax': invoice.amount_tax,
                        'amount_total': invoice.amount_total,
                        'amount_total_company_signed':invoice.amount_total_company_signed,
                        'amount_total_signed': invoice.amount_total_signed,
                        'amount_untaxed_signed': invoice.amount_untaxed_signed,
                    }             
                invoice.write(vals)
                        
                #invoice.invoice_validate()(
                #invoice.write(invoice)
                #invoice.post() 
                #invoice_line.post()
              
                #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true....?.'))
                
                actesmedicaux.write({'state': 'confirm','invoice_id':invoice.id})  
                #update = "update hospital_actesmedicaux set state = '%s',invoice_id = %s where id = %s" % ('confirm',invoice.id, actesmedicaux.id)
                #self.env.cr.execute(str(update))
                #try:
                #except ValueError:
                #    print("Error Value.")
                #except indexError:
                #    print("Erorr index")
                #except :
                #    print('error ')
                
                # La part des practiciens extérieurs
                # envisager aussi de calculer la part losque le praticien est employé 
                 
                    
                if not actesmedicaux.physician_id.employee_id: 
                    # Le practicien est quelcun de l'exterieur. Si la règle est défini alors on génere la facture d'achat de service pour ce dernier
                    
                    #actesmedicaux.write({'end_date':fields.Date.context_today(self)}) 
                                     
                        invoice_vals = {
                            'name': actesmedicaux.physician_id.partner_id.name,
                            'actesmedicaux_id': actesmedicaux.id,
                            'physician_id': actesmedicaux.physician_id.id,
                            'origin':  'Medical Act -> #%s' % (actesmedicaux.id),
                            'type': 'in_invoice',
                            'account_id': actesmedicaux.physician_id.partner_id.property_account_payable_id.id,
                            'partner_id': actesmedicaux.physician_id.partner_id.id,
                            'journal_id': journal_id,
                            'currency_id': actesmedicaux.product_id.currency_id.id,
                            'comment': '------------- ',
                            'payment_term_id': actesmedicaux.physician_id.partner_id.property_supplier_payment_term_id.id,
                            'fiscal_position_id': actesmedicaux.physician_id.partner_id.property_account_position_id.id ,
                            'company_id': actesmedicaux.physician_id.partner_id.company_id.id,
                            'user_id': actesmedicaux.create_uid.id,
                            'team_id': actesmedicaux.create_uid.team_id.id
                        }
                       
                        invoice=self.env['account.invoice'].create(invoice_vals)
                        
                        for line in actesmedicaux.actesmedicaux_lines:
                            if not line.product_id.property_account_expense_id and not line.product_id.categ_id.property_account_expense_categ_id:
                                raise osv.except_osv(_('Attention!!'),_('Please specify the expense account in the accounting tab of this Medical act or product(service).'))   
                            #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
                            #invoice= self.env['account.invoice'].browse(invoice.id) 
                            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
                            if float_is_zero(line.product_uom_qty, precision_digits=precision) or line.product_id.product_tmpl_id.type!='service':
                                continue
                            
                            percent_phisician=100
                            recs = self.env['physician.payment.term'].search(['&',('product_id', '=', line.product_id.id),('physician_id', '=', actesmedicaux.physician_id.id),('state', '=', 'activate')])
                            if not recs :
                                recs = self.env['physician.payment.term'].search(['&',('product_id', '=', line.product_id.id),('state', '=', 'activate')])
                                if not recs :
                                    recs = self.env['physician.payment.term'].search(['&',('physician_id', '=', actesmedicaux.physician_id.id),('state', '=', 'activate')])    
                                    if recs:
                                        continue 
                                    else:
                                        raise osv.except_osv(_('Configuration!!'),_('Please, for the service product %s specify the physician payment term if the physician is an external consultant or his employee id if he is an employee'%(line.product_id.name)))   
                                
                            if recs:
                                for term in recs:
                                    percent_phisician=term.percent_phisician
          
                                    
                            
                            property_account_expense_id=False
                            if line.product_id.property_account_income_id:
                                property_account_expense_id= line.product_id.property_account_expense_id.id
                            else:
                                property_account_expense_id= line.product_id.categ_id.property_account_expense_categ_id.id
                          
                            invoice_line_vals = { 
                                'name': line.product_id.name,
                                'origin': 'INV: %s => %s' % (invoice.id,actesmedicaux.patient_id.partner_id.name),
                                'sequence': 1,
                                'invoice_id': invoice.id,
                                'uom_id': line.product_id.uom_id.id,
                                'product_id': line.product_id.id,
                                'account_id': property_account_expense_id,
                                'price_unit': line.price_unit*(percent_phisician/100), #Envisager d'appeler plutot la fonction qui renvoie le prix de la liste des prix (self.lit_id.categorie_id.product_id.list_price,) 
                                'price_subtotal': line.product_uom_qty*line.price_unit*(percent_phisician/100),
                                'price_subtotal_signed': line.product_uom_qty*line.price_unit*(percent_phisician/100),
                                'quantity': line.product_uom_qty,
                                'discount': 0,
                                'company_id': actesmedicaux.physician_id.partner_id.company_id.id,
                                'partner_id': actesmedicaux.physician_id.partner_id.id,
                                'currency_id': line.product_id.currency_id.id,
                                'company_currency_id': line.product_id.currency_id.id,
                                #'invoice_line_tax_ids':
                                'account_analytic_id': False
                            } 
                            invoice_line=self.env['account.invoice.line'].create(invoice_line_vals)
                            #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
                            #invoice_line= self.env['account.invoice.line'].browse(ids_invoice_line[0])
                            invoice_line._set_taxes();
                            invoice_line._compute_price();
                            self.env['account.invoice.line'].write(invoice_line)
                        
                        invoice._onchange_invoice_line_ids();
                        invoice._compute_amount();
                        vals = { 
                                'tax_line_ids': invoice.tax_line_ids,
                                'amount_untaxed': invoice.amount_untaxed,
                                'amount_tax': invoice.amount_tax,
                                'amount_total': invoice.amount_total,
                                'amount_total_company_signed':invoice.amount_total_company_signed,
                                'amount_total_signed': invoice.amount_total_signed,
                                'amount_untaxed_signed': invoice.amount_untaxed_signed,
                            }             
                        invoice.write(vals)  
                        actesmedicaux.write({'supplier_invoice_id':invoice.id})    
                        #update = "update hospital_actesmedicaux set supplier_invoice_id = %s where id = %s" % (invoice.id, actesmedicaux.id)
                        #self.env.cr.execute(str(update))





     @api.model
     def _get_customer_lead(self, product_tmpl_id):
        return False

     @api.multi
     def button_dummy(self):
        return True

     @api.multi
     def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'sale':
            return 'sale.mt_order_confirmed'
        elif 'state' in init_values and self.state == 'sent':
            return 'sale.mt_order_sent'
        return super(HospitalactesMedicaux, self)._track_subtype(init_values)

     @api.multi
     @api.onchange('partner_shipping_id', 'partner_id')
     def onchange_partner_shipping_id(self):
        """
        Trigger the change of fiscal position when the shipping address is modified.
        """
        self.fiscal_position_id = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id, self.partner_shipping_id.id)
        return {}

     @api.multi
     def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
        if not journal_id:
            raise UserError(_('Please define an accounting sale journal for this company.'))
        invoice_vals = {
            'name': self.client_order_ref or '',
            'origin': self.name,
            'type': 'out_invoice',
            'account_id': self.partner_invoice_id.property_account_receivable_id.id,
            'partner_id': self.partner_invoice_id.id,
            'journal_id': journal_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'comment': self.note,
            'payment_term_id': self.payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id
        }
        return invoice_vals

     @api.multi
     def print_quotation(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})
        return self.env['report'].get_action(self, 'sale.report_saleorder')

     @api.multi
     def action_view_invoice(self):
        invoice_ids = self.mapped('invoice_ids')
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('account.action_invoice_tree1')
        list_view_id = imd.xmlid_to_res_id('account.invoice_tree')
        form_view_id = imd.xmlid_to_res_id('account.invoice_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'], [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(invoice_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % invoice_ids.ids
        elif len(invoice_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = invoice_ids.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

     @api.multi
     def action_invoice_create(self, grouped=False, final=False):
        """
        Create the invoice associated to the SO.
        :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        inv_obj = self.env['account.invoice']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        invoices = {}

        for order in self:
            group_key = order.id if grouped else (order.partner_invoice_id.id, order.currency_id.id)
            for line in order.actesmedicaux_lines.sorted(key=lambda l: l.qty_to_invoice < 0):
                if float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if group_key not in invoices:
                    inv_data = order._prepare_invoice()
                    invoice = inv_obj.create(inv_data)
                    invoices[group_key] = invoice
                elif group_key in invoices:
                    vals = {}
                    if order.name not in invoices[group_key].origin.split(', '):
                        vals['origin'] = invoices[group_key].origin + ', ' + order.name
                    if order.client_order_ref and order.client_order_ref not in invoices[group_key].name.split(', '):
                        vals['name'] = invoices[group_key].name + ', ' + order.client_order_ref
                    invoices[group_key].write(vals)
                if line.qty_to_invoice > 0:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)
                elif line.qty_to_invoice < 0 and final:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)

        if not invoices:
            raise UserError(_('There is no invoicable line.'))

        for invoice in invoices.values():
            if not invoice.invoice_line_ids:
                raise UserError(_('There is no invoicable line.'))
            # If invoice is negative, do a refund invoice instead
            if invoice.amount_untaxed < 0:
                invoice.type = 'out_refund'
                for line in invoice.invoice_line_ids:
                    line.quantity = -line.quantity
            # Use additional field helper function (for account extensions)
            for line in invoice.invoice_line_ids:
                line._set_additional_fields(invoice)
            # Necessary to force computation of taxes. In account_invoice, they are triggered
            # by onchanges, which are not triggered when doing a create.
            invoice.compute_taxes()

        return [inv.id for inv in invoices.values()]

     @api.multi
     def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel', 'sent'])
        orders.write({
            'state': 'draft',
            'procurement_group_id': False,
        })
        return orders.mapped('actesmedicaux_lines').mapped('procurement_ids').write({'sale_line_id': False})

     @api.multi
     def action_cancel(self):
        return self.write({'state': 'cancel'})

     @api.multi
     def action_quotation_send(self):
        '''
        This function opens a window to compose an email, with the edi sale template message loaded by default
        '''
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = ir_model_data.get_object_reference('hospital.actesmedicaux', 'email_template_edi_sale')[1]
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data.get_object_reference('mail', 'email_compose_message_wizard_form')[1]
        except ValueError:
            compose_form_id = False
        ctx = dict()
        ctx.update({
            'default_model': 'hospital.actesmedicaux',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True
        })
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

     @api.multi
     def force_quotation_send(self):
        for order in self:
            email_act = order.action_quotation_send()
            if email_act and email_act.get('context'):
                email_ctx = email_act['context']
                email_ctx.update(default_email_from=order.company_id.email)
                order.with_context(email_ctx).message_post_with_template(email_ctx.get('default_template_id'))
        return True

     @api.multi
     def action_done(self):
        return self.write({'state': 'done'})

     @api.model
     def _prepare_procurement_group(self):
        return {'name': self.name}

     @api.multi
     def action_confirm(self):
        for order in self:
            order.state = 'sale'
            if self.env.context.get('send_email'):
                self.force_quotation_send()
            order.actesmedicaux_lines._action_procurement_create()
            if not order.project_id:
                for line in order.actesmedicaux_lines:
                    if line.product_id.invoice_policy == 'cost':
                        order._create_analytic_account()
                        break
        if self.env['ir.values'].get_default('sale.config.settings', 'auto_done_setting'):
            self.action_done()
        return True

     @api.multi
     def _create_analytic_account(self, prefix=None):
        for order in self:
            name = order.name
            if prefix:
                name = prefix + ": " + order.name
            analytic = self.env['account.analytic.account'].create({
                'name': name,
                'code': order.client_order_ref,
                'company_id': order.company_id.id,
                'partner_id': order.partner_id.id
            })
            order.project_id = analytic

     @api.multi
     def _notification_group_recipients(self, message, recipients, done_ids, group_data):
        group_user = self.env.ref('base.group_user')
        for recipient in recipients:
            if recipient.id in done_ids:
                continue
            if not recipient.user_ids:
                group_data['partner'] |= recipient
            else:
                group_data['user'] |= recipient
            done_ids.add(recipient.id)
        return super(HospitalactesMedicaux, self)._notification_group_recipients(message, recipients, done_ids, group_data)
          
