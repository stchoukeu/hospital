# -*- coding: utf-8 -*-

import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import osv, fields, expression
from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare
from openerp.tools.misc import formatLang
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import UserError, RedirectWarning, ValidationError

import openerp.addons.decimal_precision as dp
import logging


class HospitalConsultation(models.Model):
     _name = 'hospital.consultation'
     _inherit = ['mail.thread']
     _description = "Consultation"
 
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
            ('consulted', 'Consulted'),
        ], string='Status', index=True, readonly=True, default='draft', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed record.\n"
             " * The 'Cancel' status is used when a user cancel the record.\n"
             " * The 'Confirm' status is used when user create the consultation and the patient is not yet consulted .\n"
             " * The 'Paid' status is set automatically when the invoice related to the number of consultation day that he made is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Consulted' status is used when the patient is consulted .\n")

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
        required=True,
        help='Physician who is(will) consult the patient',
     ) 
     prescription_id = fields.Many2one(
        string='Prescription',
        comodel_name='medical.prescription.order',
        required=False,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Prescription that is at the origin.',
     )  
     invoice_id = fields.Many2one(
        string='Invoice',
        comodel_name='account.invoice',
        required=False,
        index=True,
        readonly=True,
        help='The invoice linked with this Consultation',
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
        readonly=True,
        related='physician_id.specialty_id.product_id.list_price',
     )
  
     def _onchange_pavillon_id(self):
        if self.pavillon_id:
            self.centrehospitalier_id.id = self.pavillon_id.centrehospitalier_id.id or False
            
     @api.multi
     def name_get(self):
        result = []
        for consultation in self:
            if not consultation.invoice_id:
                #name = "[{}] {}".format(record.id, record.name)
                name = "[%s] %s" % (consultation.create_date, consultation.physician_id.name)
                result.append((consultation.id,name) )
        return result
    
     @api.multi
     @api.depends('patient_id', 'physician_id', 'invoice_id')
     def _compute_name(self):
        for consultation in self:
            name = consultation.physician_id.name
            if consultation.invoice_id:
                name = 'INV %s : %s' % (consultation.invoice_id.id,name)
            else:
                name = '%s : %s' % (consultation.create_date,name)
            consultation.name = name


     @api.model
     def create(self,values):
        values['state'] = 'draft'
        record = super(HospitalConsultation, self).create(values)
        return record 
     
     @api.multi
     def unlink(self):
        for record in self:
            if record.state == 'draft' or record.state=='cancel':
                #super(HospitalConsultation, self).unlink()
                models.Model.unlink(self)
            else:
                raise osv.except_osv(_('Attention!!'),_('You can only delete draft or cancel record'))
                #raise Warning(_('You can only delete draft or cancel record'))
     #@api.multi 
     #def write(self,values):
     #  values['state'] = 'draft'
     #  res= super(HospitalConsultation, self).write(values)
     #  return res      
   
     @api.multi
     def bouton_consulted(self):
        for consultation in self:
            invoice=consultation.invoice_id
            if not invoice or invoice.state!='paid':
                raise osv.except_osv(_('No paiement detected!!'),_('Please know that the attached bill is not paid. Please perform paiement of the bill first')) 
             
            consultation.write({'state': 'consulted'})
                                                           
     @api.multi
     def bouton_paid(self):
        for consultation in self:
            invoice=consultation.invoice_id
            if not invoice or invoice.state!='paid':
                raise osv.except_osv(_('No paiement detected!!'),_('Please know that the attached bill is not paid. Please perform paiement of the bill first')) 
                #invoice.confirm_paid()
            consultation.write({'state': 'paid'})

     @api.multi
     def bouton_cancel(self):
        for consultation in self:
            consultation.write({'state': 'cancel'})
                
     @api.multi
     def bouton_confirm(self):
                #preparing invoice
        for consultation in self:
            self.ensure_one()
            journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
            if not journal_id:
                raise osv.except_osv(_('Attention!!'),_('Please define an accounting sale journal for this company.'))
            
                #consultation.write({'end_date':fields.Date.context_today(self)}) 
                                   
            invoice_vals = {
                'name': consultation.patient_id.partner_id.name,
                'origin':  'Hospitalization -> #%s' % (consultation.id),
                'type': 'out_invoice',
                'account_id': consultation.patient_id.partner_id.property_account_receivable_id.id,
                'partner_id': consultation.patient_id.partner_id.id,
                'journal_id': journal_id,
                'currency_id': consultation.physician_id.specialty_id.product_id.currency_id.id,
                'comment': '------------- ',
                'payment_term_id': consultation.patient_id.partner_id.property_payment_term_id and consultation.patient_id.partner_id.property_payment_term_id.id,
                'fiscal_position_id': consultation.patient_id.partner_id.property_account_position_id.id ,
                'company_id': consultation.patient_id.partner_id.company_id.id,
                'user_id': consultation.create_uid and consultation.create_uid.id,
                'team_id': consultation.create_uid.team_id.id
            }
           
            invoice=self.env['account.invoice'].create(invoice_vals)
            #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
            #invoice= self.env['account.invoice'].browse(invoice.id) 
           
            
            invoice_line_vals = { 
                'name': consultation.physician_id.specialty_id.product_id.name,
                'origin': 'INV: %s => %s' % (invoice.id,consultation.patient_id.partner_id.name),
                'sequence': 1,
                'invoice_id': invoice.id,
                'uom_id': consultation.physician_id.specialty_id.product_id.uom_id.id,
                'product_id': consultation.physician_id.specialty_id.product_id.id,
                'account_id': consultation.physician_id.specialty_id.product_id.property_account_income_id.id,
                'price_unit': consultation.montant_untaxed, #Envisager d'appeler plutot la fonction qui renvoie le prix de la liste des prix (self.lit_id.categorie_id.product_id.list_price,) 
                'price_subtotal': consultation.montant_untaxed,
                'price_subtotal_signed': consultation.montant_untaxed,
                'quantity': 1,
                'discount': 0,
                'company_id': consultation.patient_id.partner_id.company_id.id,
                'partner_id': consultation.patient_id.partner_id.id,
                'currency_id': consultation.physician_id.specialty_id.product_id.currency_id.id,
                'company_currency_id': consultation.physician_id.specialty_id.product_id.currency_id.id,
                #'invoice_line_tax_ids':
                'account_analytic_id': False
            } 
            invoice_line=self.env['account.invoice.line'].create(invoice_line_vals)
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
            consultation.write({'state': 'confirm','invoice_id':invoice.id})  
              #'invoice_line_tax_ids':  //Creons les lignes de taxes conformement aux taxes sur le produit   
              #   vals = {
              #      'invoice_id': ids_invoice_line[0],
              #      'name': tax['name'],
              #      'tax_id': tax['id'],
              #      'amount': tax['amount'],
              #      'base': tax['base'],
              #      'manual': False,
              #      'sequence': tax['sequence'],
              #      'account_analytic_id': tax['analytic'] and line.account_analytic_id.id or False,
              #      'account_id': self.type in ('out_invoice', 'in_invoice') and (tax['account_id'] or line.account_id.id) or (tax['refund_account_id'] or line.account_id.id),
              #  }
                # If the taxes generate moves on the same financial account as the invoice line,
                # propagate the analytic account from the invoice line to the tax line.
                # This is necessary in situations were (part of) the taxes cannot be reclaimed,
                # to ensure the tax move is allocated to the proper analytic account.
              #  if not vals.get('account_analytic_id') and line.account_analytic_id and vals['account_id'] == line.account_id.id:
              #      vals['account_analytic_id'] = line.account_analytic_id.id 
              
            consultation.print_report()
        
     @api.multi
     def print_report(self):
        return {
        'type' : 'ir.actions.report',
        'report_name': 'report_patient_template_card',
        'datas': {
           'ids': [ self.id ],
           'model': 'hospital.consultation'
            }
        }