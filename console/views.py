import re

from vrtManager.util import randomUUID

from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from libvirt import libvirtError

from accounts.models import UserInstance
from appsettings.settings import app_settings
from instances.models import Instance
from vrtManager.instance import wvmInstance
from webvirtcloud.settings import (
    WS_PATH,
    SOCKETIO_PATH,
)


def console(request):
    """
    :param request:
    :return:
    """
    console_error = None

    if request.method == "GET":
        token = request.GET.get("token", "")
        view_type = request.GET.get("view", "lite")
        view_only = request.GET.get("view_only", app_settings.CONSOLE_VIEW_ONLY.lower())
        scale = request.GET.get("scale", app_settings.CONSOLE_SCALE.lower())
        resize_session = request.GET.get(
            "resize_session", app_settings.CONSOLE_RESIZE_SESSION.lower()
        )
        clip_viewport = request.GET.get(
            "clip_viewport", app_settings.CONSOLE_CLIP_VIEWPORT.lower()
        )

    try:
        temptoken = token.split("-", 1)
        host = int(temptoken[0])
        uuid = temptoken[1]

        if not request.user.is_superuser and not request.user.has_perm(
            "instances.view_instances"
        ):
            try:
                userInstance = UserInstance.objects.get(
                    instance__compute_id=host,
                    instance__uuid=uuid,
                    user__id=request.user.id,
                )
                instance = Instance.objects.get(compute_id=host, uuid=uuid)
            except UserInstance.DoesNotExist:
                instance = None
                console_error = _(
                    "User does not have permission to access console or host/instance not exist"
                )
                return HttpResponseServerError(console_error)
        else:
            instance = Instance.objects.get(compute_id=host, uuid=uuid)

        conn = wvmInstance(
            instance.compute.hostname,
            instance.compute.login,
            instance.compute.password,
            instance.compute.type,
            instance.name,
        )
        console_type = conn.get_console_type()
        console_websocket_port = conn.get_console_websocket_port()
        console_passwd = conn.get_console_passwd()
    except libvirtError:
        console_type = None
        console_websocket_port = None
        console_passwd = None

    ws_path = WS_PATH if WS_PATH else "/"

    if console_type == "vnc" or console_type == "spice":
        console_page = "console-" + console_type + "-" + view_type + ".html"
        response = render(request, console_page, locals())
    elif console_type == "pty":
        socketio_path = SOCKETIO_PATH if SOCKETIO_PATH else "/"
        response = render(request, "console-xterm.html", locals())
    else:
        if console_type is None:
            console_error = _(
                "Fail to get console. Please check the console configuration of your VM."
            )
        else:
            console_error = _("Console type '%(type)s' has not support") % {
                "type": console_type
            }
        response = render(request, "console-vnc-lite.html", locals())

    response.set_cookie("token", token)
    return response
