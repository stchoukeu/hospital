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


class HospitalPavillon(models.Model):
     _name = 'hospital.pavillon'
     _inherit = ['mail.thread']
     _description = "Pavillon for Hospitalization"
 
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
        default=lambda s: s._default_name(),
        states={'draft': [('readonly', False)]},
     )
     centrehospitalier_id = fields.Many2one(
        string='Hospital Center',
        comodel_name='hospital.centrehospitalier',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='The hospital center.',
     )
     salle_ids = fields.One2many(
        comodel_name='hospital.salle',
        inverse_name='pavillon_id',
        string='Roms',
          help='The list of rooms that are in the hospital center.',
     ) 
     physician_id = fields.Many2one(
        string='Chief Manager',
        comodel_name='medical.physician',
        required=True,
        help='Physician who is the responsible',
     ) 
    
     start_date = fields.Date(
        string="Start date ",
        help='The physician position occupation start date ',
     )
     _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Name must be unique!'),
     ] 
     @api.model
     def _default_name(self):
        return self.env['ir.sequence'].next_by_code(
            'hospital.pavillon',
        ) 