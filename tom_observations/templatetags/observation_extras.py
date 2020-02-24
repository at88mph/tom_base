from urllib.parse import urlencode

from django import forms, template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from plotly import offline
import plotly.graph_objs as go

from tom_observations.models import ObservationRecord
from tom_observations.facility import get_service_classes
from tom_observations.observing_strategy import RunStrategyForm
from tom_targets.models import Target


register = template.Library()


@register.inclusion_tag('tom_observations/partials/observing_buttons.html')
def observing_buttons(target):
    """
    Displays the observation buttons for all facilities available in the TOM.
    """
    facilities = get_service_classes()
    return {'target': target, 'facilities': facilities}


@register.inclusion_tag('tom_observations/partials/observation_type_tabs.html', takes_context=True)
def observation_type_tabs(context):
    """
    Displays tabs in observation creation form representing each available observation type.
    """
    request = context['request']
    query_params = request.GET.copy()
    observation_type = query_params.pop('observation_type', None)
    return {
        'params': urlencode(query_params),
        'type_choices': context['type_choices'],
        'observation_type': observation_type,
        'facility': context['form']['facility'].value,
        'target_id': request.GET.get('target_id')
    }


@register.inclusion_tag('tom_observations/partials/observation_list.html', takes_context=True)
def observation_list(context, target=None):
    """
    Displays a list of all observations in the TOM, limited to an individual target if specified.
    """
    if target:
        if settings.ROW_LEVEL_PERMISSIONS:
            observations = get_objects_for_user(
                                context['request'].user,
                                'tom_observations.view_observationrecord'
                            ).filter(target=target)
        else:
            observations = target.observationrecord_set.all()
    else:
        observations = ObservationRecord.objects.all().order_by('-created')
    return {'observations': observations}


@register.inclusion_tag('tom_observations/partials/observingstrategy_run.html')
def observingstrategy_run(target):
    """
    Renders the form for running an observing strategy.
    """
    form = RunStrategyForm(initial={'target': target})
    form.fields['target'].widget = forms.HiddenInput()
    return {'form': form}


@register.inclusion_tag('tom_observations/partials/observingstrategy_from_record.html')
def observingstrategy_from_record(obsr):
    """
    Renders a button that will pre-populate and observing strategy form with parameters from the specified
    ``ObservationRecord``.
    """
    params = urlencode(obsr.parameters_as_dict)
    return {
        'facility': obsr.facility,
        'params': params
    }


@register.inclusion_tag('tom_observations/partials/observation_distribution.html')
def observation_distribution(observations):
    """
    Displays a plot showing on a map the locations of all observations recorded in the TOM.
    """

    # "distinct" query is not supported, must manually find distinct observation per target
    sorted_observations = observations.order_by('scheduled_end')  # ascending so that only the max is preserved
    observation_targets = {}
    for obs in sorted_observations:
        observation_targets[obs.target_id] = (obs.status, obs.terminal)

    observation_no_status = [t for t in observation_targets.keys()
                             if not observation_targets[t][0]]  # status==""
    observation_terminal = [t for t in observation_targets.keys()
                            if observation_targets[t][0]
                            and observation_targets[t][1]]  # status!="" and terminal
    observation_non_terminal = [t for t in observation_targets.keys()
                                if observation_targets[t][0]
                                and not observation_targets[t][1]]  # status!="" and not terminal

    targets_no_status = Target.objects.filter(pk__in=observation_no_status)
    targets_terminal = Target.objects.filter(pk__in=observation_terminal)
    targets_non_terminal = Target.objects.filter(pk__in=observation_non_terminal)

    locations_no_status = targets_no_status.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    locations_terminal = targets_terminal.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')
    locations_non_terminal = targets_non_terminal.filter(type=Target.SIDEREAL).values_list('ra', 'dec', 'name')

    data = [
        dict(
            lon=[l[0] for l in locations_no_status],
            lat=[l[1] for l in locations_no_status],
            text=[l[2] for l in locations_no_status],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker=dict(color='rgba(90, 90, 90, .8)'),
            type='scattergeo'
        ),
        dict(
            lon=[l[0] for l in locations_non_terminal],
            lat=[l[1] for l in locations_non_terminal],
            text=[l[2] for l in locations_non_terminal],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker=dict(color='rgba(152, 0, 0, .8)'),
            type='scattergeo'
        ),
        dict(
            lon=[l[0] for l in locations_terminal],
            lat=[l[1] for l in locations_terminal],
            text=[l[2] for l in locations_terminal],
            hoverinfo='lon+lat+text',
            mode='markers',
            marker=dict(color='rgba(0, 152, 0, .8)'),
            type='scattergeo'
        ),
        dict(
            lon=list(range(0, 360, 60))+[180]*4,
            lat=[0]*6+[-60, -30, 30, 60],
            text=list(range(0, 360, 60))+[-60, -30, 30, 60],
            hoverinfo='none',
            mode='text',
            type='scattergeo'
        )
    ]
    layout = {
        'title': 'Observation Distribution (sidereal)',
        'hovermode': 'closest',
        'showlegend': False,
        'geo': {
            'projection': {
                'type': 'mollweide',
            },
            'showcoastlines': False,
            'showland': False,
            'lonaxis': {
                'showgrid': True,
                'range': [0, 360],
            },
            'lataxis': {
                'showgrid': True,
                'range': [-90, 90],
            },
        }
    }
    figure = offline.plot(go.Figure(data=data, layout=layout), output_type='div', show_link=False)
    return {'figure': figure}
