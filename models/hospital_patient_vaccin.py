# -*- coding: utf-8 -*-
# Copyright 2017 Toolter Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
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


class MedicalPatientVaccin(models.Model):
    _name = 'hospital.patient.vaccin'
    _description = 'Patient Vaccin'
    
    name = fields.Char(
        compute='_compute_name',
        store=True,
    )
    state = fields.Selection(
        string='Status',
        selection=[
            ('a', 'Acute'),
            ('c', 'Chronic'),
            ('u', 'Unchanged'),
            ('h', 'Healed'),
            ('i', 'Improving'),
            ('w', 'Worsening'),
        ],
        help='Status of this disease.',
    )
    description = fields.Char()
    comment = fields.Char()
    expire_date = fields.Datetime(
        string='Date Expired',
        compute='_compute_expire_date',
        store=True,
    )
    pathology_id = fields.Many2one(
        string='Pathology',
        comodel_name='medical.pathology',
        index=True,
        required=True,
        help='Pathology (disease type) the patient was vaccined against.',
    )
    physician_id = fields.Many2one(
        string='Physician',
        comodel_name='medical.physician',
        index=True,
        help='Physician who administrated a Vaccin.',
    )
    patient_id = fields.Many2one(
        string='Patient',
        comodel_name='medical.patient',
        required=True,
        index=True,
        help='Patient that was vaccined.',
    )
    duree = fields.Integer(
        string='Vaccin live times',
        help='Vaccin live times.',
    )
    age = fields.Integer(
        string='Age When Taken a vaccin',
        help='Age of the patient when diagnosed with this disease.',
    )
    active = fields.Boolean(
        default=True,
        help='Uncheck this box to deactivate.',
    )
    start_date = fields.Date(
        string="Date Vaccin Starts",
        help='If the patient is receiving treatment'
             ' state the start date here.',
    )
    end_date = fields.Date(
        string='Date Vaccin Ends',
        help='If the patient is/was receiving treament'
             ' state the end date here.',
    )
    notes = fields.Text(
        help='Any additional information that may be helpful.',
    )

    @api.multi
    @api.depends('short_comment', 'pathology_id', 'pathology_id.name')
    def _compute_name(self):
        for rec_id in self:
            name = rec_id.pathology_id.name
            if rec_id.short_comment:
                name = '%s - %s' % (name, rec_id.short_comment)
            rec_id.name = name

    @api.multi
    @api.depends('active')
    def _compute_expire_date(self):
        for rec_id in self:
            if rec_id.active:
                rec_id.expire_date = False
            else:
                rec_id.expire_date = fields.Datetime.now()

    @api.multi
    def action_invalidate(self):
        for rec_id in self:
            rec_id.active = False

    @api.multi
    def action_revalidate(self):
        for rec_id in self:
            rec_id.active = True
