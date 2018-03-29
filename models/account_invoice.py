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



class AccountInvoice(models.Model):
    _name = 'account.invoice'
    _inherit = ['account.invoice']
     
    physician_id = fields.Many2one(
        string='Physician',
        comodel_name='medical.physician',
        required=False,
        help='Physician who is at the origin of this bill',
    ) 
    actemedical_id = fields.Many2one(
        string='Medical Act From',
        comodel_name='hospital.actemedical',
        required=False,
        help=' The medical act at the origin of this bill',
    ) 