# -*- coding: utf-8 -*-

import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.osv import osv, expression
from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare
from openerp.tools.misc import formatLang

from openerp.exceptions import UserError, RedirectWarning, ValidationError

import openerp.addons.decimal_precision as dp
import logging


class PhysicianPaymentTerm(models.Model):
     _name = 'physician.payment.term'
     _inherit = ['mail.thread']
     _description = "Hospitalization paiement terms for physicians. Regarding of their activities"
 
     state = fields.Selection([
            ('draft','Draft'),
            ('cancel','Canceled'),
            ('activate', 'Activated'),
        ], string='Status', index=True, readonly=True, default='draft',
        copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unactivated rule.\n"
             " * The 'Cancel' status is used when a user cancel a rule.\n"
             " * The 'Activate' status is used when user confirm the rule .\n")
     
     physician_id = fields.Many2one(
        string='Physician',
        comodel_name='medical.physician',
        readonly=True,
        required=False,
        states={'draft': [('readonly', False)]},
        help='Physician who is(will) consult the patient',
     ) 
     department_id = fields.Many2one(
        comodel_name='hr.department',
        readonly=True,
        required=False,
        string='HR Departement',
        ondelete='set null',
        states={'draft': [('readonly', False)]},
        help="The HR department. If set, the rulle will be  \n"\
             " applied to every physician(Employee) that in the department.  ",
     )   
     product_id = fields.Many2one(
        comodel_name='product.product',
        readonly=True,
        required=True,
        string='Service product',
        ondelete='set null',
        states={'draft': [('readonly', False)]},
        help='The Product (service).',
     )   
     centrehospitalier_id = fields.Many2one(
        string='Hospital Center',
        comodel_name='hospital.centrehospitalier',
        required=False,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='The hospital center.',
     )
     percent_phisician = fields.Float(
        string='Physician Percentage part',
        readonly=True,
         states={'draft': [('readonly', False)]},
        help=' Specified the percentage of the physician,'\
             ' who made this service',
     ) 
     percent_service = fields.Float(
        string='Department Percentage part',
        readonly=True,
         states={'draft': [('readonly', False)]},
        help=' Specified the percentage that will be distribuate to all,'\
             ' members of the department',
     )
     _sql_constraints = [
        ('rule_uniq', 'UNIQUE(physician_id,product_id,centrehospitalier_id)', 'This rule must be unique!'),
     ]    

     @api.multi
     def bouton_activate(self):
        for hospitalisation in self:
            if hospitalisation.percent_phisician==0 and hospitalisation.percent_service==0:
                raise osv.except_osv(_('Attention!!'),_('Please a percentage must be > 0 or you delete this rule.')) 
            else:
                hospitalisation.write({'state': 'activate'})

     @api.multi
     def bouton_cancel(self):
        for hospitalisation in self:
            hospitalisation.write({'state': 'cancel'})