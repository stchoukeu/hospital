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



class HospitalCentrehospitalier(models.Model):
     _name = 'hospital.centrehospitalier'
     _inherit = ['mail.thread']
     _description = "Hospital Center"

     state = fields.Selection([
            ('draft','Draft'),
            ('confirm', 'Confirmed'),
        ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed record.\n"
             " * The 'Confirmed' status is used when user confirm the record .\n")
               
     name = fields.Char(
        required=True,
        readonly=True,
        translate=True,
        select=True,
        states={'draft': [('readonly', False)]},
     )
     pavillon_ids = fields.One2many(
        comodel_name='hospital.pavillon',
        inverse_name='centrehospitalier_id',
        string='Pavillons',
     )
     physician_id = fields.Many2one(
        string='Manager',
        comodel_name='medical.physician',
        required=True,
        help='Physician who is the principal',
     ) 
     _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Name must be unique!'),
     ] 