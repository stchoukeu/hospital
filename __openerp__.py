# -*- coding: utf-8 -*-
{
    'name': "hospital",

    'summary': """
        Manage hospitalization by providing Bed, Pavillon, Medical Center and functions to hospitalize patient
        consultation, etc...""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Toolter",
    'website': "http://www.toolter.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Hospial Management Systems',
    'version': '0.1',

    # any module necessary for this one to work correctly  
    'depends': ['medical','medical_medication','medical_physician','medical_prescription','medical_pharmacy','account','report','medical_patient_disease_allergy','sale','product','medical_lab','hr_payroll','hr_expense','purchase'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/hospital_categorie_salle.xml',
        'views/hospital_centrehospitalier.xml',
        'views/hospital_hospitalisation.xml',
        'views/hospital_consultation.xml',
        'views/hospital_lit.xml',
        'views/hospital_pavillon.xml',
        'views/hospital_salle.xml',
        'views/medical_menu.xml',
        'views/medical_specialty.xml',
        'views/medical_patient.xml',
        'views/medical_physician.xml',
        'report/patient_card_report_view.xml',
        'views/hospital_patient_disease.xml',
        'views/account_invoice.xml',
        'views/physician_payment_term.xml',
        'views/hospital_actemedical.xml',
        'views/hospital_actesmedicaux.xml',
        'views/hospital_actesmedicaux_line.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable' : True,
    'application' : True,
}