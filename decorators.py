# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 CRS4
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
General-purpose decorators for use with Horizon.
"""
import functools

from django.utils.decorators import available_attrs  # noqa
from django.utils.translation import ugettext_lazy as _
import tomograph


def _current_component(view_func, dashboard=None, panel=None):
    """Sets the currently-active dashboard and/or panel on the request."""
    @functools.wraps(view_func, assigned=available_attrs(view_func))
    def dec(request, *args, **kwargs):
        if dashboard:
            request.horizon['dashboard'] = dashboard
        if panel:
            request.horizon['panel'] = panel
        if not tomograph.tracing_started():
            span_host = tomograph.getHost()
            ser_name = "%s[%s]" % (view_func.__module__, view_func.__name__)
            tomograph.start(ser_name, view_func.__name__, span_host, 0)
            ret = view_func(request, *args, **kwargs)
            tomograph.stop(view_func.__name__)
            return ret
        return view_func(request, *args, **kwargs)
    return dec

def require_auth(view_func):
    """Performs user authentication check.

    Similar to Django's `login_required` decorator, except that this throws
    :exc:`~horizon.exceptions.NotAuthenticated` exception if the user is not
    signed-in.
    """
    from horizon.exceptions import NotAuthenticated  # noqa

    @functools.wraps(view_func, assigned=available_attrs(view_func))
    def dec(request, *args, **kwargs):
        if request.user.is_authenticated():
            return view_func(request, *args, **kwargs)
        raise NotAuthenticated(_("Please log in to continue."))
    return dec


def require_perms(view_func, required):
    """Enforces permission-based access controls.

    :param list required: A tuple of permission names, all of which the request
                          user must possess in order access the decorated view.

    Example usage::

        from horizon.decorators import require_perms


        @require_perms(['foo.admin', 'foo.member'])
        def my_view(request):
            ...

    Raises a :exc:`~horizon.exceptions.NotAuthorized` exception if the
    requirements are not met.
    """
    from horizon.exceptions import NotAuthorized  # noqa
    # We only need to check each permission once for a view, so we'll use a set
    current_perms = getattr(view_func, '_required_perms', set([]))
    view_func._required_perms = current_perms | set(required)

    @functools.wraps(view_func, assigned=available_attrs(view_func))
    def dec(request, *args, **kwargs):
        if request.user.is_authenticated():
            if request.user.has_perms(view_func._required_perms):
                return view_func(request, *args, **kwargs)
        raise NotAuthorized(_("You are not authorized to access %s")
                            % request.path)

    # If we don't have any permissions, just return the original view.
    if required:
        return dec
    else:
        return view_func
