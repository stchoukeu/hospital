# -*- coding: utf-8 -*-
from openerp import http

# class Hospitalcare(http.Controller):
#     @http.route('/hospitalcare/hospitalcare/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hospitalcare/hospitalcare/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('hospitalcare.listing', {
#             'root': '/hospitalcare/hospitalcare',
#             'objects': http.request.env['hospitalcare.hospitalcare'].search([]),
#         })

#     @http.route('/hospitalcare/hospitalcare/objects/<model("hospitalcare.hospitalcare"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hospitalcare.object', {
#             'object': obj
#         })