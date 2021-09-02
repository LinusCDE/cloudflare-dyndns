import os
import CloudFlare
import waitress
import flask
import ipv6util

app = flask.Flask(__name__)


@app.route('/', methods=['GET'])
def main():
    token = flask.request.args.get('token')
    zone = flask.request.args.get('zone')
    record = flask.request.args.get('record')
    ipv4 = flask.request.args.get('ipv4')
    ipv6 = flask.request.args.get('ipv6')
    ipv6prefix = flask.request.args.get('ipv6prefix')
    cf = CloudFlare.CloudFlare(token=token)

    if not token:
        return flask.jsonify({'status': 'error', 'message': 'Missing token URL parameter.'}), 400
    if not zone:
        return flask.jsonify({'status': 'error', 'message': 'Missing zone URL parameter.'}), 400
    if not record:
        return flask.jsonify({'status': 'error', 'message': 'Missing record URL parameter.'}), 400
    if not ipv4 and not ipv6 and not ipv6prefix:
        return flask.jsonify({'status': 'error', 'message': 'Missing ipv4, ipv6 or ipv6prefix URL parameter.'}), 400
    if ipv6 and ipv6prefix:
        return flask.jsonify({'status': 'error', 'message': 'Only ipv6 or ipv6prefix supported. Not both.'}), 400

    try:
        zones = cf.zones.get(params={'name': zone})

        if not zones:
            return flask.jsonify({'status': 'error', 'message': 'Zone {} does not exist.'.format(zone)}), 404

        a_record = cf.zones.dns_records.get(zones[0]['id'], params={
                                            'name': '{}.{}'.format(record, zone), 'match': 'all', 'type': 'A'})
        aaaa_record = cf.zones.dns_records.get(zones[0]['id'], params={
                                               'name': '{}.{}'.format(record, zone), 'match': 'all', 'type': 'AAAA'})

        if ipv4 is not None and not a_record:
            return flask.jsonify({'status': 'error', 'message': 'A record for {}.{} does not exist.'.format(record, zone)}), 404

        if (ipv6 is not None or ipv6prefix is not None) and not aaaa_record:
            return flask.jsonify({'status': 'error', 'message': 'AAAA record for {}.{} does not exist.'.format(record, zone)}), 404

        if ipv4 is not None and a_record[0]['content'] != ipv4:
            cf.zones.dns_records.put(zones[0]['id'], a_record[0]['id'], data={
                                     'name': a_record[0]['name'], 'type': 'A', 'content': ipv4})

        if ipv6 is not None and aaaa_record[0]['content'] != ipv6:
            cf.zones.dns_records.put(zones[0]['id'], aaaa_record[0]['id'], data={
                                     'name': aaaa_record[0]['name'], 'type': 'AAAA', 'content': ipv6})

        if ipv6prefix is not None:
            original_ipv6 = ipv6util.IPv6(aaaa_record[0]['content'])
            new_ipv6_prefix = ipv6util.IPv6(ipv6prefix)
            if new_ipv6_prefix.net_bit_count == 128:
                # If no netmask was given (/xxx) at the end, assume /48
                new_ipv6_prefix.net_bit_count = 48
            new_ipv6 = original_ipv6.modifiedPrefix(new_ipv6_prefix)
            if original_ipv6 != new_ipv6:
                cf.zones.dns_records.put(zones[0]['id'], aaaa_record[0]['id'], data={
                                         'name': aaaa_record[0]['name'], 'type': 'AAAA', 'content': new_ipv6.ip()})
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        return flask.jsonify({'status': 'error', 'message': str(e)}), 500

    return flask.jsonify({'status': 'success', 'message': 'Update successful.'}), 200


if __name__ == '__main__':
    app.secret_key = os.urandom(24)
    waitress.serve(app, host='0.0.0.0', port=80)
