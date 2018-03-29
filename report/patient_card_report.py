# -*- coding: utf-8 -*-

from openerp import tools
from openerp import models, fields, api
import time
from openerp.osv import osv
from openerp.report import report_sxw


class PatientCardReport(models.AbstractModel):
    _name = "report.hospital.report_patient_card_template_id"
    #  _name = 'report.your_addon.report_template_id'
    _description = "Patient card"
    _auto = False
    #_rec_name = 'date'

    @api.multi
    def render_html(self, data=None):
        report_obj = self.env['report']
        report = report_obj._get_report_from_name('hospital.report_template_id')
        model_patient_docs = self.env['medical.patient'].search([('something','=','something')])
        model_lit_docs = self.env['hospital.lit'].search([('something','=','something')])   
        
        docargs = {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': self,
            'model_patient_docs': model_patient_docs,
            'model_lit_docs': model_lit_docs,
        }
        return report_obj.render('hospital.report_patient_card_template_id', docargs)