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



class HospitalHospitalisation(models.Model):
     _name = 'hospital.hospitalisation'
     _inherit = ['mail.thread']
     _description = "Patient Hospitalization"
     _order = 'id desc'
   
     state = fields.Selection([
            ('draft','Draft'),
            ('cancel', 'Cancel'),
            ('confirm', 'Confirm'),
            ('out', 'Out'),
            ('paid', 'Paid'),
            
        ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed hospitalization.\n"
             " * The 'Canceled' status is used when user cancel invoice."
             " * The 'Confirm' status is used when user create hospitalization,a number is generated and the patient occupied a bed in the hospital \n"
             " * The 'Out' status is used when user choise to specified that a patient leave a room that he was occupied in the hospital \n"
             " * The 'Paid' status is set automatically when the invoice related to the number of hospitalisation day that he made is paid. Its related journal entries may or may not be reconciled.\n"
     )
     
     patient_id = fields.Many2one(
        string='Patient',
        comodel_name='medical.patient',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Patient that is ill and still be hospitalised.',
     )
     consultation_id = fields.Many2one(
        string='First Consultation',
        comodel_name='hospital.consultation',
        required=False,
        index=True,
        readonly=True,
      #  domain=[('patient_id', '=', patient_id)],
        states={'draft': [('readonly', False)],'confirm': [('readonly', False)],'out': [('readonly', False)]},
        help='The first consultation',
     )
     lit_id = fields.Many2one(
        string='Bed',
        comodel_name='hospital.lit',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)],'confirm': [('readonly', False)]},
        help='Bed occupied by the Patient.',
     )
     salle_id = fields.Many2one(
        string='Room',
        related='lit_id.salle_id',
        comodel_name='hospital.salle',
        required=False,
        index=True,
        readonly=True,
        help='Room where the patient is located.',
     )
     pavillon_id = fields.Many2one(
        string='Pavillon(Batiment)',
        related='lit_id.salle_id.pavillon_id',
        comodel_name='hospital.pavillon',
        required=False,
        index=True,
        readonly=True,
        help='Pavillon where the patient is located.',
     )
    
     centrehospitalier_id = fields.Many2one(
        string='Hospital Center',
        related='lit_id.salle_id.pavillon_id.centrehospitalier_id',
        comodel_name='hospital.centrehospitalier',
        required=False,
        index=True,
        readonly=True,
        help='Hospital Center where the patient is located.',
     )
     invoice_id = fields.Many2one(
        string='Invoice',
        comodel_name='account.invoice',
        required=False,
        index=True,
        readonly=True,
        help='The invoice linked with this hospitalization',
     )
     start_date = fields.Date(
        string="Hospitalisation Start Date",
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='If the patient is Hospitalized '\
             ' state the start date here.',
     )
     end_date = fields.Date(
        string='Hospitalisation End Date',
        readonly=True,
        states={'confirm': [('readonly', False)]},
        help='If the patient is/was Hospitalized'\
             ' state the end date here.',
     )
     admission_reason = fields.Text(
        string='Admission Reason', 
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Why the patient is/was Hospitalized',
     )
     nbre_jours = fields.Float(
        string='Number of day(s)',
        compute='calcul_nbre_jours',
        readonly=True,
        store=True,
        help='Number of hosptalization days.',
     )
       
     unit_price = fields.Float(
        string='Amount per day',
        related='lit_id.salle_id.categorie_id.unit_price',
        readonly=True,
        help=' Base on the standing of the room,'\
             ' Amount paid per Day',
     )
     montant_total_untaxed = fields.Float(string='Total untaxed', 
        store=True, readonly=True, compute='_compute_montant_total_untaxed')
     
     currency_id = fields.Many2one(
        string='Currency',
        comodel_name='res.currency',
        required=False,
        index=True,
        readonly=True,
        help='The Price Currency.',
     )

     @api.one
     @api.depends('start_date', 'end_date','lit_id')
     def _compute_montant_total_untaxed(self):
        for hospitalisation in self:
          if hospitalisation.lit_id and hospitalisation.start_date and hospitalisation.end_date:
            if  hospitalisation.start_date<=hospitalisation.end_date:
                d1 = datetime.strptime(hospitalisation.end_date, DEFAULT_SERVER_DATE_FORMAT)
                d2 = datetime.strptime(hospitalisation.start_date, DEFAULT_SERVER_DATE_FORMAT)
                #daysDiff = (d2-d1).days
                hospitalisation.nbre_jours =round((d1 - d2).days)
                hospitalisation.montant_total_untaxed = hospitalisation.lit_id.salle_id.categorie_id.unit_price *(round((d1-d2).days))
            else:
                raise osv.except_osv(_('Attention'),_(' End date must be greater than start date.'))
     # onchange triggered when modified lit_id
     @api.onchange('lit_id')
     def _onchange_lit_id(self):
         for hospitalisation in self:
            hospitalisation.salle_id = hospitalisation.lit_id.salle_id.id or False
            hospitalisation.pavillon_id = hospitalisation.lit_id.salle_id.pavillon_id.id or False
            hospitalisation.centrehospitalier_id = hospitalisation.lit_id.salle_id.pavillon_id.centrehospitalier_id.id or False
            hospitalisation.unit_price = hospitalisation.lit_id.salle_id.categorie_id.unit_price
            hospitalisation.currency_id = hospitalisation.lit_id.salle_id.categorie_id.currency_id
     @api.one
     @api.depends('start_date', 'end_date')   
     def calcul_nbre_jours(self):
        for hospitalisation in self:
            if hospitalisation.end_date and hospitalisation.start_date:
                if  hospitalisation.start_date<=hospitalisation.end_date:
                    d1 = datetime.strptime(hospitalisation.end_date, DEFAULT_SERVER_DATE_FORMAT)
                    d2 = datetime.strptime(hospitalisation.start_date, DEFAULT_SERVER_DATE_FORMAT)
                    #daysDiff = (d2-d1).days
                    hospitalisation.nbre_jours =round((d1 - d2).days)
                    
     @api.model
     def create(self,values):
        values['state'] = 'draft'
        record = super(HospitalHospitalisation, self).create(values)
        return record 
     
     @api.multi
     def unlink(self):
        for record in self:
            if record.state == 'draft' or record.state=='cancel':
                #super(HospitalHospitalisation, self).unlink()
                models.Model.unlink(self)
            else:
                raise osv.except_osv(_('Attention!!'),_('You can only delete draft or cancel record'))
                #raise Warning(_('You can only delete draft or cancel record'))
     #@api.multi 
     #def write(self,values):
     #  values['state'] = 'draft'
     #  res= super(HospitalHospitalisation, self).write(values)
     #  return res      
     
     @api.multi
     def bouton_confirm(self):
        for hospitalisation in self:
            if not hospitalisation.start_date:
                raise osv.except_osv(_('Attention!!'),_('Please set a start date.')) 
            else:
                hospitalisation.write({'state': 'confirm'})
                                                           
     @api.multi
     def bouton_paid(self):
        for hospitalisation in self:
            invoice=hospitalisation.invoice_id
            if not invoice or invoice.state!='paid':
                raise osv.except_osv(_('No paiement detected!!'),_('Please know that the attached bill is not paid. Please perform paiement of the bill first')) 
                #invoice.confirm_paid()
            hospitalisation.write({'state': 'paid'})

     @api.multi
     def bouton_cancel(self):
        for hospitalisation in self:
            hospitalisation.write({'state': 'cancel'})
                
     @api.multi
     def bouton_out(self):
                #preparing invoice
        for hospitalisation in self:
            self.ensure_one()
            journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
            if not journal_id:
                raise osv.except_osv(_('Attention!!'),_('Please define an accounting sale journal for this company.'))
            
            if not hospitalisation.end_date :
                raise osv.except_osv(_('Attention!!'),_('Please set the end date.')) 
                #hospitalisation.write({'end_date':fields.Date.context_today(self)}) 
                
                             
            invoice_vals = {
                'name': hospitalisation.patient_id.partner_id.name,
                'origin':  'Hospitalization -> #%s' % (hospitalisation.id),
                'type': 'out_invoice',
                'account_id': hospitalisation.patient_id.partner_id.property_account_receivable_id.id,
                'partner_id': hospitalisation.patient_id.partner_id.id,
                'journal_id': journal_id,
                'currency_id': hospitalisation.lit_id.salle_id.categorie_id.currency_id.id,
                'comment': '------------- ',
                'payment_term_id': hospitalisation.patient_id.partner_id.property_payment_term_id and hospitalisation.patient_id.partner_id.property_payment_term_id.id,
                'fiscal_position_id': hospitalisation.patient_id.partner_id.property_account_position_id.id ,
                'company_id': hospitalisation.patient_id.partner_id.company_id.id,
                'user_id': hospitalisation.create_uid and hospitalisation.create_uid.id,
                'team_id': hospitalisation.create_uid.team_id.id
            }
           
            invoice=self.env['account.invoice'].create(invoice_vals)
            #raise osv.except_osv(_('INVOICE %s' % (invoice.id)),_(' Is it the true?.'))
            #invoice= self.env['account.invoice'].browse(invoice.id) 
           
            
            invoice_line_vals = { 
                'name': hospitalisation.lit_id.salle_id.categorie_id.product_id.name,
                'origin': 'INV: %s => %s' % (invoice.id,hospitalisation.patient_id.partner_id.name),
                'sequence': 1,
                'invoice_id': invoice.id,
                'uom_id': hospitalisation.lit_id.salle_id.categorie_id.product_id.uom_id.id,
                'product_id': hospitalisation.lit_id.salle_id.categorie_id.product_id.id,
                'account_id': hospitalisation.lit_id.salle_id.categorie_id.product_id.property_account_income_id.id,
                'price_unit': hospitalisation.unit_price, #Envisager d'appeler plutot la fonction qui renvoie le prix de la liste des prix (self.lit_id.categorie_id.product_id.list_price,) 
                'price_subtotal': hospitalisation.montant_total_untaxed,
                'price_subtotal_signed': hospitalisation.montant_total_untaxed,
                'quantity': hospitalisation.nbre_jours,
                'discount': 0,
                'company_id': hospitalisation.patient_id.partner_id.company_id.id,
                'partner_id': hospitalisation.patient_id.partner_id.id,
                'currency_id': hospitalisation.lit_id.salle_id.categorie_id.product_id.currency_id.id,
                'company_currency_id': hospitalisation.lit_id.salle_id.categorie_id.product_id.currency_id.id,
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
          
            #raise osv.except_osv(_('INVOICE %s' % (facture.id)),_(' Is it the true?.'))
            hospitalisation.write({'state': 'out','invoice_id':invoice.id})  
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
        
    
    