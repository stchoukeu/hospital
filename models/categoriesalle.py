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
import openerp.addons.decimal_precision as dp
import logging


class HospitalCategoriesalle(models.Model):
     _name = 'hospital.categoriesalle'
     _inherit = ['mail.thread']
     _description = "Room Category"
 
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
     unit_price = fields.Float(
       # compute='_get_unit_price', 
        related='product_id.list_price',
        string='Amount per day',
        digits_compute=dp.get_precision('Product Price'),
      #  currency_field='currency_id',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help=" Base on the standing of the room,\n"
             " Specified the amount to buy per Day",
     )
    
     salle_ids = fields.One2many(
        comodel_name='hospital.salle',
        inverse_name='categorie_id',
        string='Room(s)',
     )
     product_id = fields.Many2one(
        comodel_name='product.product',
        readonly=True,
        required=True,
        string='Product',
        ondelete='set null',
        states={'draft': [('readonly', False)]},
        index=True)
     currency_id = fields.Many2one(
       # compute='_get_currency',
        related='product_id.company_id.currency_id',
        string='Currency',
        comodel_name='res.currency',
        help='The Price Currency.',
     )      
     _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Name must be unique!'),
     ] 
     #currency_id= fields.function(_category_currency, type='many2one', relation='res.currency', string='Currency')
     # onchange triggered when modified lit_id
     #@api.onchange('product_id')
     def _category_currency(self):
        for category in self:
            if category.product_id: 
                if category.product_id.company_id and category.product_id.company_id.currency_id: 
                    category.currency_id = category.product_id.company_id.currency_id
                else:
                    raise UserError(_('Data error!\n Cannot catch a currency?'))
                category.unit_price= category.product_id.list_price

     def bouton_confirm(self, cr, uid, vals, context=None):
        vals['state']='confirm'
        #self.write({'state': 'confirm'})    
        return self.write(cr, uid, vals, context)  
                       
     @api.model
     def _default_name(self):
        return self.env['ir.sequence'].next_by_code(
            'hospital.categoriesalle',
        )
        
     @api.depends('product_id')   
     def _get_currency(self):
        for record in self:
            record.currency_id = record.product_id.company_id.currency_id
     @api.depends('product_id')
     def _get_unit_price(self):
        for record in self:
            record.unit_price = record.product_id.list_price
   