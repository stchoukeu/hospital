# -*- coding: utf-8 -*-
# Copyright 2017 TCHOUKEU Simplice Aimé
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


class MedicalPatient(models.Model):
    _name = 'medical.patient'
    _inherit = ['medical.patient']

    consultation_ids = fields.One2many(
        comodel_name='hospital.consultation',
        inverse_name='patient_id',
        string='Consultation(s)',
    )
    hospitalisation_ids = fields.One2many(
        comodel_name='hospital.hospitalisation',
        inverse_name='patient_id',
        string='Hospitalization(s)',
    )
    count_hospitalisation_ids = fields.Integer(
        string='Hospitalization',
        compute='_compute_count_hospitalisation_ids',
    )
    count_consultation_ids = fields.Integer(
        string='Consultation',
        compute='_compute_count_consultation_ids',
    )
    @api.multi
    def _compute_count_hospitalisation_ids(self):
        for rec_id in self:
            rec_id.count_hospitalisation_ids = len(rec_id.hospitalisation_ids)
    @api.multi
    def _compute_count_consultation_ids(self):
        for rec_id in self:
            rec_id.count_consultation_ids = len(rec_id.consultation_ids)