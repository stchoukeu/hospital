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

from openerp.exceptions import UserError, RedirectWarning, ValidationError

import openerp.addons.decimal_precision as dp
import logging


class MedicalSpecialty(models.Model):
    _name = 'medical.specialty'
    _inherit = ['medical.specialty']

    product_id = fields.Many2one(
        string='Consultation Service Product',
        comodel_name='product.product',
        required=True,
        index=True,
        readonly=False,
        help='The consultation Service Product',
    )