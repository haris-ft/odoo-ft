# -*- coding: utf-8 -*-

from odoo import api, fields,models


class FeeTemplate(models.Model):
    _name = 'fee.template'

    name = fields.Char(string="Template Name")



