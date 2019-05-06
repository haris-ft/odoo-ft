odoo.define('smart_accounting.systray', function (require) {
"use strict";

var SystrayMenu = require('web.SystrayMenu');
var Widget = require('web.Widget');

var ActivityNewPayment = Widget.extend({
    template:'smart_accounting.ActivityNewPayment',
    sequence: 200,
    events: {
        "click": "_onActivityMenuClick"
    },
    _onActivityMenuClick: function () {
        this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'fee.account.payment',
                view_mode: 'tree',
                views: [[false, 'form']],
                target: 'new',
                context: {},
            });
    },
});

SystrayMenu.Items.push(ActivityNewPayment);

});