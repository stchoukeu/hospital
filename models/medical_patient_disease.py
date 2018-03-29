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


class MedicalPatientDisease(models.Model):
    _name = 'medical.patient.disease'
    _inherit = ['medical.patient.disease']

    consultation_id = fields.Many2one(
        string='Consultation',
        comodel_name='hospital.consultation',
        required=False,
        index=True,
        readonly=True,
        help='The consultation',
    )
    medicament_id = fields.Many2one(
        string='Medicament(in case of allergy)',
        comodel_name='medical.medicament',
        required=False,
        index=True,
        help='The Medicament that have produce an allergy',
    )
    is_allergy = fields.Boolean(
        string='Allergic Disease',
        required=False,
        readonly=False,
        store=True,
        help='Check this box to indicate that the disease is an allergy.',
    )