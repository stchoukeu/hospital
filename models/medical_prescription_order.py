# -*- coding: utf-8 -*-
# Copyright 2016 LasLabs Inc.
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


class MedicalPrescriptionOrder(models.Model):
    _inherit = 'medical.prescription.order'

    receive_method = fields.Selection(
        string='Receive Method',
        selection=[
            ('online', 'E-Prescription'),
            ('phone', 'Phoned In'),
            ('fax', 'Fax'),
            ('mail', 'Physical Mail'),
            ('transfer', 'Transferred In'),
        ],
        default='fax',
        help='How the Rx was received',
    )
    verify_method = fields.Selection(
        string='Verification Method',
        selection=[
            ('none', 'Not Verified'),
            ('doctor_phone', 'Called Doctor'),
        ],
        default='none',
        help='Method of Rx verification',
    )
    receive_date = fields.Datetime(
        string='Receive Date',
        default=fields.Datetime.now,
        help='When the Rx was received',
    )
    verify_user_id = fields.Many2one(
        string='Verify User',
        comodel_name='res.users',
        store=True,
        compute='_compute_verified',
        help='User that verified the prescription',
    )
    verify_date = fields.Datetime(
        string='Verification Date',
        store=True,
        compute='_compute_verified',
        help='When the prescription was verified',
    )
    is_verified = fields.Boolean(
        string='Verified',
        store=True,
        compute='_compute_verified',
        help='If checked, this prescription has been confirmed as valid',
    )
    transfer_pharmacy_id = fields.Many2one(
        string='Transfer Pharmacy',
        comodel_name='medical.pharmacy',
    )
    transfer_direction = fields.Selection(
        string='Transfer Direction',
        selection=[
            ('none', 'None'),
            ('in', 'In'),
            ('out', 'Out'),
        ],
        default='none',
    )
    transfer_ref = fields.Char(
        string='Transfer Reference',
    )

    @api.multi
    @api.depends('verify_method')
    def _compute_verified(self):
        for record in self:
            if record.verify_method != 'none':
                if not record.is_verified:
                    record.is_verified = True
                    record.verify_user_id = self.env.user.id
                    record.verify_date = fields.Datetime.now()
