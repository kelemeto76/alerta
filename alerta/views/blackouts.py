
from flask import current_app, g, jsonify, request
from flask_cors import cross_origin

from alerta.app import qb
from alerta.auth.decorators import permission
from alerta.exceptions import ApiError
from alerta.models.blackout import Blackout
from alerta.models.enums import Scope
from alerta.utils.api import assign_customer
from alerta.utils.audit import write_audit_trail
from alerta.utils.response import absolute_url, jsonp

from . import api


@api.route('/blackout', methods=['OPTIONS', 'POST'])
@cross_origin()
@permission(Scope.write_blackouts)
@jsonp
def create_blackout():
    try:
        blackout = Blackout.parse(request.json)
    except Exception as e:
        raise ApiError(str(e), 400)

    if Scope.admin in g.scopes or Scope.admin_blackouts in g.scopes:
        blackout.user = blackout.user or g.user
    else:
        blackout.user = g.user

    blackout.customer = assign_customer(wanted=blackout.customer, permission=Scope.admin_blackouts)

    try:
        blackout = blackout.create()
    except Exception as e:
        raise ApiError(str(e), 500)

    write_audit_trail.send(current_app._get_current_object(), event='blackout-created', message='', user=g.user,
                           customers=g.customers, scopes=g.scopes, resource_id=blackout.id, type='blackout', request=request)

    if blackout:
        return jsonify(status='ok', id=blackout.id, blackout=blackout.serialize), 201, {'Location': absolute_url('/blackout/' + blackout.id)}
    else:
        raise ApiError('insert blackout failed', 500)


@api.route('/blackouts', methods=['OPTIONS', 'GET'])
@cross_origin()
@permission(Scope.read_blackouts)
@jsonp
def list_blackouts():
    query = qb.from_params(request.args)
    blackouts = Blackout.find_all(query)

    if blackouts:
        return jsonify(
            status='ok',
            blackouts=[blackout.serialize for blackout in blackouts],
            total=len(blackouts)
        )
    else:
        return jsonify(
            status='ok',
            message='not found',
            blackouts=[],
            total=0
        )


@api.route('/blackout/<blackout_id>', methods=['OPTIONS', 'DELETE'])
@cross_origin()
@permission(Scope.write_blackouts)
@jsonp
def delete_blackout(blackout_id):
    customer = g.get('customer', None)
    blackout = Blackout.find_by_id(blackout_id, customer)

    if not blackout:
        raise ApiError('not found', 404)

    write_audit_trail.send(current_app._get_current_object(), event='blackout-deleted', message='', user=g.user,
                           customers=g.customers, scopes=g.scopes, resource_id=blackout.id, type='blackout', request=request)

    if blackout.delete():
        return jsonify(status='ok')
    else:
        raise ApiError('failed to delete blackout', 500)
