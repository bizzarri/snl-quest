from __future__ import absolute_import

import json
import collections
import logging
import copy
import calendar

import numpy as np

from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
from kivy.properties import ObjectProperty, BooleanProperty, StringProperty, DictProperty
from kivy.app import App
from kivy.animation import Animation
from kivy.uix.stencilview import StencilView

from es_gui.resources.widgets.common import InputError, WarningPopup, MyPopup, ValuationRunCompletePopup, RecycleViewRow, FADEIN_DUR
from es_gui.tools.valuation.valuation_optimizer import BadParameterException
from es_gui.apps.data_manager.data_manager import DataManagerException

bx_anim = Animation(transition='out_expo', duration=FADEIN_DUR, opacity=1)

class ValuationBatchRunScreenManager(ScreenManager):
    def __init__(self, **kwargs):
        super(ValuationBatchRunScreenManager, self).__init__(**kwargs)

        # Add new screens here.
        self.add_widget(BatchRunDataScreen(name='data'))
        self.add_widget(BatchRunParamScreen(name='params'))


class BatchRunScreen(Screen):
    def on_enter(self):
        # Change the navigation bar title.
        ab = self.manager.nav_bar
        ab.build_valuation_batch_nav_bar()
        ab.set_title('Batch Runs')

    def _generate_requests(self):
        data_screen = self.batch_sm.get_screen('data')
        params_screen = self.batch_sm.get_screen('params')

        rv_selected, months, iso, rev_streams, node = data_screen.get_inputs()
        param_settings = params_screen.get_inputs()

        requests = {'iso': iso,
                    'market type': rev_streams,
                    'months': months,
                    'node id': node['nodeid'],
                    'param set': param_settings
                    }

        return requests

    def run_batch(self):
        try:
            requests = self._generate_requests()
        except ValueError as e:
            popup = WarningPopup()
            popup.popup_text.text = str(e)
            popup.open()
        except InputError as e:
            popup = WarningPopup()
            popup.popup_text.text = str(e)
            popup.open()
        else:
            solver_name = App.get_running_app().config.get('optimization', 'solver')

            handler = self.manager.get_screen('valuation_home').handler
            handler.solver_name = solver_name

            try:
                _, handler_status = handler.process_requests(requests)
            except BadParameterException as e:
                popup = WarningPopup()
                popup.popup_text.text = str(e)
                popup.open()
            else:
                self.completion_popup = BatchRunCompletePopup()
                self.completion_popup.view_results_button.bind(on_release=self._go_to_view_results)

                if not handler_status:
                    self.completion_popup.title = "Success!*"
                    self.completion_popup.popup_text.text = "Your specified batch runs have been completed.\n\n*At least one model (month) had issues being built and/or solved. Any such model will be omitted from the results."

                self.completion_popup.open()            

    def _go_to_view_results(self, *args):
        self.manager.nav_bar.go_to_screen('plot')
        self.completion_popup.dismiss()


class BatchRunParamScreen(Screen):
    iso = StringProperty('')
    param_to_attr = dict()

    def on_pre_enter(self):
        self.iso = self.manager.get_screen('data').iso

    def on_iso(self, instance, value):
        while len(self.param_widget.children) > 0:
            for widget in self.param_widget.children:
                if isinstance(widget, BatchRunParameterRow):
                    self.param_widget.remove_widget(widget)
    
        if self.iso:
            try:
                self.param_widget.build(self.iso)

                data_manager = App.get_running_app().data_manager
                MODEL_PARAMS = data_manager.get_valuation_model_params(value)

                self.param_to_attr = {param['name']: param['attr name']
                                      for param in MODEL_PARAMS}
                self.param_sweep_spinner.values = ['none',] + list(self.param_to_attr.keys())
            except KeyError:
                pass

    def _disable_text_input(self, text):
        # Disables the text input field of the parameter selected for a parameter sweep.
        for row_widget in self.param_widget.children:
            row_widget.text_input.disabled = False

        attr_name = self.param_to_attr.get(text, '')

        if attr_name:
            param_widget_row = getattr(self.param_widget, attr_name, None)
            param_widget_row.text_input.disabled = True

    def _validate_inputs(self):
        # If a parameter sweep is specified, check all input fields.
        param_sweep_name = self.param_sweep_spinner.text

        if self.param_to_attr.get(param_sweep_name, False):
            try:
                param_min = float(self.param_min_input.text)
                param_max = float(self.param_max_input.text)
                param_step = int(self.param_step_input.text)
            except ValueError:
                raise InputError('All range input fields must be populated when specifying a parameter sweep.')
            else:
                if param_max < param_min:
                    raise InputError('Parameter sweep minimum must be less than or equal to the maximum.')
        else:
            if any([self.param_min_input.text, self.param_max_input.text, self.param_step_input.text]):
                raise InputError('Did you forget to provide a parameter for the parameter sweep? Numbers for the sweep range were provided but no parameter was given.')

    def get_inputs(self):
        self._validate_inputs()

        base_param_dict = {}

        # Check for any input into the parameter rows.
        for param_row in self.param_widget.children:
            param_name = param_row.name.text

            if param_row.text_input.text:
                param_value = float(param_row.text_input.text)
                base_param_dict[self.param_to_attr[param_name]] = param_value

        param_settings = []

        param_sweep_name = self.param_sweep_spinner.text

        if self.param_to_attr.get(param_sweep_name, False):
            param_min = float(self.param_min_input.text)
            param_max = float(self.param_max_input.text)
            param_step = int(self.param_step_input.text)
            param_sweep_range = np.linspace(param_min, param_max, num=param_step)

            for param_sweep_value in param_sweep_range:
                base_copy = copy.deepcopy(base_param_dict)
                base_copy[self.param_to_attr[param_sweep_name]] = float(param_sweep_value)
                param_settings.append(base_copy)
        else:
            param_settings.append(base_param_dict)

        return param_settings


class BatchRunDataScreen(Screen):
    iso = StringProperty('')
    rev_streams = StringProperty('')
    node = DictProperty()

    def __init__(self, **kwargs):
        super(BatchRunDataScreen, self).__init__(**kwargs)

        BatchRVNodeEntry.host_screen = self
    
    def _get_iso_options(self):
        try:
            data_manager = App.get_running_app().data_manager
        except AttributeError:
            pass
        else:
            iso_options = data_manager.get_markets()
            self.iso_select.values = iso_options

    def _reset_screen(self):
        self.revstreams_select.opacity = 0.05
        self.months_select_bx.opacity = 0.05
        self.node_select_bx.opacity = 0.05

        # Deselects all RV selections.
        self.month_rv.deselect_all_nodes()
        self.node_rv.deselect_all_nodes()

        # Resets properties.
        self.rev_streams = ''
        self.node = {}

    def _iso_selected(self):
        self.iso = self.iso_select.text
        self.revstreams_select.text = 'Select revenue streams'

        try:
            # Get available pricing nodes.
            data_manager = App.get_running_app().data_manager
            nodes = data_manager.get_nodes(self.iso)

            node_options = [{'name': node[1],
                             'nodeid': node[0]} for node in nodes.items()]

            self.node_rv.data = node_options
            self.node_rv.unfiltered_data = node_options
        except KeyError:
            # The ISO selected has no valid nodes.
            node_options = [{}]
        else:
            # Enable node selector.
            bx_anim.start(self.node_select_bx)

    def on_iso(self, instance, value):
        logging.info('ValuationBatch: ISO changed to {0}.'.format(value))

        self._reset_screen()

    def _revstreams_selected(self):
        try:
            data_manager = App.get_running_app().data_manager
            market_models_available = data_manager.get_valuation_revstreams(self.iso, self.node['nodeid'])
            self.rev_streams = market_models_available[self.revstreams_select.text]['market type']
        except KeyError:
            self.rev_streams = ''
        else:
            # Get available historical data.
            historical_data_all = data_manager.get_historical_data_options(self.iso, self.node['nodeid'], self.revstreams_select.text)
            historical_data_opts = []

            for (year, month_list) in historical_data_all.items():
                month_options = [{'name': '{month} {year}'.format(month=calendar.month_name[int(month)], year=year),
                'month': month, 'year': year} for month in month_list]
                historical_data_opts.extend(month_options)
            
            self.month_rv.data = historical_data_opts
            bx_anim.start(self.months_select_bx)

    def on_rev_streams(self, instance, value):
        if value:
            logging.info('ValuationBatch: Revenue streams changed to {0}.'.format(value))
        else:
            logging.info('ValuationBatch: Revenue streams selection reset.')

    def on_node(self, instance, value):
        try:
            logging.info('ValuationBatch: Pricing node changed to {0}.'.format(self.node['name']))
        except KeyError:
            logging.info('ValuationBatch: Pricing node selection reset.')
        else:
            # Get available revenue streams.
            try:
                data_manager = App.get_running_app().data_manager
                market_models_available = data_manager.get_valuation_revstreams(self.iso, value['nodeid'])
                self.revstreams_select.values = market_models_available.keys()
            except (KeyError, DataManagerException):
                self.revstreams_select.values = []
            else:
                # Enable revenue stream selector and reset it.
                bx_anim.start(self.revstreams_select)
                self.revstreams_select.text = 'Select revenue streams'
                self.revstreams_select.disabled = False
            
            # Reset historical data options.
            self._revstreams_selected()
            self.month_rv.deselect_all_nodes()
            self.month_rv.data = []

    def _validate_inputs(self):
        if self.iso_select.text == 'Select market area':
            raise (InputError('No market area selected.'))

        if self.revstreams_select.text == 'Select revenue streams':
            raise (InputError('No revenue streams selected.'))

        if not self.node:
            raise (InputError('No pricing node selected.'))

        rv_selected = [self.month_rv.data[selected_ix] for selected_ix in self.month_rv.layout_manager.selected_nodes]

        if not rv_selected:
            raise (InputError('No data selected.'))

    def get_inputs(self):
        self._validate_inputs()

        # Retrieve selected months from recycle view.
        rv_selected = [self.month_rv.data[selected_ix] for selected_ix in self.month_rv.layout_manager.selected_nodes]

        months = [(selected_entry['month'], selected_entry['year']) for
                  selected_entry in rv_selected]

        return rv_selected, months, self.iso, self.rev_streams, self.node


class BatchRunParameterRow(GridLayout):
    """Grid layout containing parameter descriptor label, slider, and value label."""

    def __init__(self, desc, **kwargs):
        super(BatchRunParameterRow, self).__init__(**kwargs)

        self._desc = desc
        self.name.text = self.desc['name']
        self.text_input.hint_text = str(self.desc['default'])

    @property
    def desc(self):
        return self._desc

    @desc.setter
    def desc(self, value):
        self._desc = value


class BatchRunParameterWidget(GridLayout):
    """Grid layout containing rows of parameter adjustment widgets."""
    def __init__(self, **kwargs):
        super(BatchRunParameterWidget, self).__init__(**kwargs)

    def build(self, iso):
        # Build the widget by creating a row for each parameter.
        data_manager = App.get_running_app().data_manager
        MODEL_PARAMS = data_manager.get_valuation_model_params(iso)

        for param in MODEL_PARAMS:
            row = BatchRunParameterRow(desc=param)
            self.add_widget(row)
            setattr(self, param['attr name'], row)


class BatchParamTextInput(TextInput):
    """
    A TextInput field for entering parameter value sweep range descriptors. Limited to float values.
    """
    def insert_text(self, substring, from_undo=False):
        # limit to 8 chars
        substring = substring[:8 - len(self.text)]
        return super(BatchParamTextInput, self).insert_text(substring, from_undo=from_undo)


class BatchRVNodeEntry(RecycleViewRow):
    host_screen = None

    def apply_selection(self, rv, index, is_selected):
        """
        Respond to the selection of items in the view.
        """
        super(BatchRVNodeEntry, self).apply_selection(rv, index, is_selected)

        if is_selected:
            self.host_screen.node = rv.data[self.index]
        # else:
        #     self.host_screen.node = ''


class BatchRunCompletePopup(ValuationRunCompletePopup):
    def __init__(self, **kwargs):
        super(BatchRunCompletePopup, self).__init__(**kwargs)

        self.popup_text.text = 'Your specified batch runs have been completed.'
