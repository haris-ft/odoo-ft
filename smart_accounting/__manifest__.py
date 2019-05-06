# -*- coding: utf-8 -*-
{
    "name":  "Smart Accounting",
    "summary":  "Accounting for smart school",
    "category":  "tools",
    "version":  "1.0",
    "sequence":  1,
    "description":  """Accounting for smart school""",
    "depends":  ['base', 'account_invoicing', 'smartschool_base'],
    "data":  [
        'data/smart_accounting_data.xml',
        'views/ss_fees_type_view.xml',
        'views/fee_structure_view.xml',
        'views/fee_group_view.xml',
        'views/ss_student_view.xml',
        'views/ss_fee_payment_views.xml',
        'views/ss_fee_views.xml',
        'views/res_config_settings_view.xml',
        'views/templates.xml',
        'wizard/collection_report_view_wzd.xml',
        'views/ss_accounting_menus.xml',
        'reports/fee_collection_report.xml',
        'reports/payment_receipt.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    "application":  False,
    "installable":  True,
    "auto_install":  False,
}

