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



class HospitalLit(models.Model):
     _name = 'hospital.lit'
     _inherit = ['mail.thread']
     _description = "Bed for Hospitalisation"
   
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
     salle_id = fields.Many2one(
        string='Room',
        comodel_name='hospital.salle',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Room where this bed is located.',
     )
     pavillon_id = fields.Many2one(
        string='Pavillon',
        related='salle_id.pavillon_id',
        comodel_name='hospital.pavillon',
        required=False,
        index=True,
        readonly=True,
        help='Pavillon where this room is located.',
     )
     centrehospitalier_id = fields.Many2one(
        string='Hospital Center',
        related='salle_id.pavillon_id.centrehospitalier_id',
        comodel_name='hospital.centrehospitalier',
        required=False,
        index=True,
        readonly=True,
        help='The hospital center.',
     )   
     buy_date = fields.Date(
        string="Buy date ",
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='The date that we buy this bed ',
     )
     _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Name must be unique!'),
     ] 
     @api.onchange('salle_id')
     def _onchange_salle_id(self):
        for lit in self:
            lit.pavillon_id = lit.salle_id.pavillon_id or False
            lit.centrehospitalier_id = lit.salle_id.pavillon_id.centrehospitalier_id.id or False
     @api.model
     def _default_name(self):
        return self.env['ir.sequence'].next_by_code(
            'hospital.lit',
        )
     @api.multi
     def name_get(self):
        result = []
        for lit in self:
            if  lit.salle_id:
                #name = "[{}] {}".format(record.id, record.name)
                display_name = "%s[%s][%s]" % (lit.name,lit.salle_id.categorie_id.name, lit.salle_id.name)
                result.append((lit.id,display_name) )
        return result