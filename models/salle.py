# -*- coding: utf-8 -*-

import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta

from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare
from openerp.tools.misc import formatLang

from openerp.exceptions import UserError, RedirectWarning, ValidationError

import openerp.addons.decimal_precision as dp
import logging


class HospitalSalle(models.Model):
     _name = 'hospital.salle'
     _inherit = ['mail.thread']
     _description = "Room for Hospitalization"
 
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
     pavillon_id = fields.Many2one(
        string='Pavillon',
        comodel_name='hospital.pavillon',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Pavillon where this room is located.',
     ) 
     categorie_id = fields.Many2one(
        string='Room Category',
        comodel_name='hospital.categoriesalle',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Categorie of this room.',
     )
     lit_ids = fields.One2many(
        comodel_name='hospital.lit',
        inverse_name='salle_id',
        string='Bed(s)',
     )
     centrehospitalier_id = fields.Many2one(
        string='Hospital Center',
        comodel_name='hospital.centrehospitalier',
        required=False,
        index=True,
        readonly=True,
        help='The hospital center.',
     )
     _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Name must be unique!'),
     ]    
     @api.onchange('pavillon_id')
     def _onchange_pavillon_id(self):
        if self.pavillon_id and self.pavillon_id.centrehospitalier_id:
            self.centrehospitalier_id = self.pavillon_id.centrehospitalier_id or False
     
     @api.model
     def _default_name(self):
        return self.env['ir.sequence'].next_by_code(
            'hospital.salle',
        )