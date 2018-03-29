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



class HospitalActemedical(models.Model):
     _name = 'hospital.actemedical'
    # _inherit = ['mail.thread']
     _description = "Salle Acte Medical"
 
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
     product_id = fields.Many2one(
        comodel_name='product.product',
        readonly=True,
        required=True,
        string='Product',
        ondelete='set null',
        states={'draft': [('readonly', False)]},
        index=True
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
     
     disease_ids = fields.One2many(
        comodel_name='medical.patient.disease',
        inverse_name='consultation_id',
        string='Bed(s)',
     )
     montant_untaxed = fields.Float(
        string='Amount untaxed', 
        store=True, 
        readonly=False,
        related='product_id.list_price',
     )
  
     #def _onchange_pavillon_id(self):
     #   if self.pavillon_id:
     #       self.centrehospitalier_id.id = self.pavillon_id.centrehospitalier_id.id or False
            
     @api.multi
     def name_get(self):
        result = []
        for actemedical in self:
            if not actemedical.invoice_id:
                #name = "[{}] {}".format(record.id, record.name)
                name = "[%s] %s" % (actemedical.create_date, actemedical.physician_id.name)
                result.append((actemedical.id,name) )
        return result
    
     @api.multi
     @api.depends('patient_id', 'physician_id', 'invoice_id')
     def _compute_name(self):
        for actemedical in self:
            name = actemedical.product_id.name
            if actemedical.invoice_id:
                name = 'INV %s : %s' % (actemedical.invoice_id.id,name)
            else:
                name = '%s : %s' % (actemedical.create_date,name)
            actemedical.name = name


     @api.model
     def create(self,values):
        values['state'] = 'draft'
        record = super(HospitalActemedical, self).create(values)
        return record 
     
     @api.multi
     def unlink(self):
        for record in self:
            if record.state == 'draft' or record.state=='cancel':
                #super(HospitalActemedical, self).unlink()
                models.Model.unlink(self)
            else:
                raise osv.except_osv(_('Attention!!'),_('You can only delete draft or cancel record'))
                #raise Warning(_('You can only delete draft or cancel record'))
     #@api.multi 
     #def write(self,values):
     #  values['state'] = 'draft'
     #  res= super(HospitalActemedical, self).write(values)
     #  return res      
   
     @api.multi
     def bouton_delivered(self):
        for actemedical in self:
            invoice=actemedical.invoice_id
            if not invoice or invoice.state!='paid':
                raise osv.except_osv(_('No paiement detected!!'),_('Please know that the attached bill is not paid. Please perform paiement of the bill first')) 
             
            actemedical.write({'state': 'delivered'})
                                                           
     @api.multi
     def bouton_paid(self):
        for actemedical in self:
            invoice=actemedical.invoice_id
            if not invoice or invoice.state!='paid':
                raise osv.except_osv(_('No paiement detected!!'),_('Please know that the attached bill is not paid. Please perform paiement of the bill first')) 
                #invoice.confirm_paid()
            actemedical.write({'state': 'paid'})

     @api.multi
     def bouton_cancel(self):
        for actemedical in self:
            actemedical.write({'state': 'cancel'})
                
     @api.multi
     def bouton_confirm(self):
                #preparing invoice
        for actemedical in self:
            self.ensure_one()
            journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
            if not journal_id:
                raise osv.except_osv(_('Attention!!'),_('Please define an accounting sale journal for this company.'))
            if not actemedical.product_id.property_account_income_id and not actemedical.product_id.categ_id.property_account_income_categ_id:
                raise osv.except_osv(_('Attention!!'),_('Please specify the revenue account in the accounting tab of this Medical act or product(service).'))  
                #actemedical.write({'end_date':fields.Date.context_today(self)}) 
                                   
            invoice_vals = {
                'name': actemedical.patient_id.partner_id.name,
                'actemedical_id': actemedical.id,
                'physician_id': actemedical.physician_id.id,
                'origin':  'Hospitalization -> #%s' % (actemedical.id),
                'type': 'out_invoice',
                'account_id': actemedical.patient_id.partner_id.property_account_receivable_id.id,
                'partner_id': actemedical.patient_id.partner_id.id,
                'journal_id': journal_id,
                'currency_id': actemedical.product_id.currency_id.id,
                'comment': '------------- ',
                'payment_term_id': actemedical.patient_id.partner_id.property_payment_term_id.id,
                'fiscal_position_id': actemedical.patient_id.partner_id.property_account_position_id.id ,
                'company_id': actemedical.patient_id.partner_id.company_id.id,
                'user_id': actemedical.create_uid.id,
                'team_id': actemedical.create_uid.team_id.id
            }
           
            invoice=self.env['account.invoice'].create(invoice_vals)
            
            #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
            #invoice= self.env['account.invoice'].browse(invoice.id) 
            property_account_income_id=False
            if actemedical.product_id.property_account_income_id:
                property_account_income_id= actemedical.product_id.property_account_income_id.id
            else:
                property_account_income_id= actemedical.product_id.categ_id.property_account_income_categ_id.id
            
            invoice_line_vals = { 
                'name': actemedical.product_id.name,
                'origin': 'INV: %s => %s' % (invoice.id,actemedical.patient_id.partner_id.name),
                'sequence': 1,
                'invoice_id': invoice.id,
                'uom_id': actemedical.product_id.uom_id.id,
                'product_id': actemedical.product_id.id,
                'account_id': property_account_income_id,
                'price_unit': actemedical.montant_untaxed, #Envisager d'appeler plutot la fonction qui renvoie le prix de la liste des prix (self.lit_id.categorie_id.product_id.list_price,) 
                'price_subtotal': actemedical.montant_untaxed,
                'price_subtotal_signed': actemedical.montant_untaxed,
                'quantity': 1,
                'discount': 0,
                'company_id': actemedical.patient_id.partner_id.company_id.id,
                'partner_id': actemedical.patient_id.partner_id.id,
                'currency_id': actemedical.product_id.currency_id.id,
                'company_currency_id': actemedical.product_id.currency_id.id,
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
            
            #invoice.invoice_validate()
            #invoice.write(invoice)
            #invoice.post() 
            #invoice_line.post()
          
            #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true....?.'))
            actemedical.write({'state': 'confirm','invoice_id':invoice.id})  
            
            if not actemedical.physician_id.employee_id:
                # Le practicien est quelcun de l'exterieur. Si la règle est défini alors on génere la facture d'achat de service pour ce dernier
                if not actemedical.product_id.property_account_expense_id and not actemedical.product_id.categ_id.property_account_expense_categ_id:
                    raise osv.except_osv(_('Attention!!'),_('Please specify the expense account in the accounting tab of this Medical act or product(service).'))
                
                    #actemedical.write({'end_date':fields.Date.context_today(self)}) 
                montant_achat=actemedical.montant_untaxed
                recs = self.env['physician.payment.term'].search(['&',('product_id', '=', actemedical.product_id.id),('physician_id', '=', actemedical.physician_id.id)])
                if recs: 
                    for term in recs:
                        montant_achat=montant_achat*term.percent_phisician                          
                    invoice_vals = {
                        'name': actemedical.physician_id.partner_id.name,
                        'actemedical_id': actemedical.id,
                        'physician_id': actemedical.physician_id.id,
                        'origin':  'Medical Act -> #%s' % (actemedical.id),
                        'type': 'in_invoice',
                        'account_id': actemedical.physician_id.partner_id.property_account_payable_id.id,
                        'partner_id': actemedical.physician_id.partner_id.id,
                        'journal_id': journal_id,
                        'currency_id': actemedical.product_id.currency_id.id,
                        'comment': '------------- ',
                        'payment_term_id': actemedical.physician_id.partner_id.property_supplier_payment_term_id.id,
                        'fiscal_position_id': actemedical.physician_id.partner_id.property_account_position_id.id ,
                        'company_id': actemedical.physician_id.partner_id.company_id.id,
                        'user_id': actemedical.create_uid.id,
                        'team_id': actemedical.create_uid.team_id.id
                    }
                   
                    invoice=self.env['account.invoice'].create(invoice_vals)
                    
                    #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
                    #invoice= self.env['account.invoice'].browse(invoice.id) 
                    property_account_expense_id=False
                    if actemedical.product_id.property_account_income_id:
                        property_account_expense_id= actemedical.product_id.property_account_expense_id.id
                    else:
                        property_account_expense_id= actemedical.product_id.categ_id.property_account_expense_categ_id.id
                  
                    invoice_line_vals = { 
                        'name': actemedical.product_id.name,
                        'origin': 'INV: %s => %s' % (invoice.id,actemedical.patient_id.partner_id.name),
                        'sequence': 1,
                        'invoice_id': invoice.id,
                        'uom_id': actemedical.product_id.uom_id.id,
                        'product_id': actemedical.product_id.id,
                        'account_id': property_account_expense_id,
                        'price_unit': montant_achat, #Envisager d'appeler plutot la fonction qui renvoie le prix de la liste des prix (self.lit_id.categorie_id.product_id.list_price,) 
                        'price_subtotal': montant_achat,
                        'price_subtotal_signed': montant_achat,
                        'quantity': 1,
                        'discount': 0,
                        'company_id': actemedical.physician_id.partner_id.company_id.id,
                        'partner_id': actemedical.physician_id.partner_id.id,
                        'currency_id': actemedical.product_id.currency_id.id,
                        'company_currency_id': actemedical.product_id.currency_id.id,
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
                    actemedical.write({'supplier_invoice_id':invoice.id})              
