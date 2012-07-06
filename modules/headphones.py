from flask import jsonify, render_template, json, send_file
from maraschino import app, logger, WEBROOT, RUNDIR
from maraschino.tools import requires_auth, get_setting_value
from threading import Thread
import StringIO
import urllib
import urllib2
import base64


def headphones_api(command, use_json=True, dev=False):
    hostname = get_setting_value('headphones_host')
    port = get_setting_value('headphones_port')
    username = get_setting_value('headphones_user')
    password = get_setting_value('headphones_password')
    apikey = get_setting_value('headphones_api')

    url = 'http://%s:%s/api?apikey=%s&cmd=%s' % (hostname, port, apikey, command)

    request = urllib2.Request(url)
    base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    data = urllib2.urlopen(request).read()

    if use_json:
        data = json.JSONDecoder().decode(data)

    if dev:
        print 'DEVELOPER :: %s' % url
        print 'DEVELOPER :: %s' % data

    return data


def convert_track_duration(milliseconds):
    if milliseconds is None:
        return "00:00"
    seconds = milliseconds / 1000
    hours = seconds / 3600
    seconds -= 3600 * hours
    minutes = seconds / 60
    seconds -= 60 * minutes
    if hours == 0:
        return "%02d:%02d" % (minutes, seconds)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def hp_compact():
    return get_setting_value('headphones_compact') == '1'


def headphones_url():
    url = 'http://'

    hostname = get_setting_value('headphones_host')
    port = get_setting_value('headphones_port')
    username = get_setting_value('headphones_user')
    password = get_setting_value('headphones_password')

    if len(password) > 0:
        url += '%s:%s@' % (username, password)

    url += '%s:%s' % (hostname, port)
    return url


def headphones_exception(e):
    logger.log('HEADPHONES :: EXCEPTION -- %s' % e, 'DEBUG')
    return render_template('headphones-base.html', headphones=True, message=e)


def hp_artistart(id):
    return '%s/xhr/headphones/img/artist/%s' % (WEBROOT, id)


def hp_albumart(id):
    return '%s/xhr/headphones/img/album/%s' % (WEBROOT, id)


@app.route('/xhr/headphones/img/<type>/<id>/')
@requires_auth
def xhr_headphones_image(type, id):
    if type == 'artist':
        cache_url = headphones_api('getArtistThumb&id=' + id)
    else:
        cache_url = headphones_api('getAlbumThumb&id=' + id)

    if cache_url:
        url = '%s/%s' % (headphones_url(), cache_url)
    else:
        img = RUNDIR + '/static/images/applications/HeadPhones.png'
        return send_file(img, mimetype='image/jpeg')

    img = StringIO.StringIO(urllib.urlopen(url).read())
    return send_file(img, mimetype='image/jpeg')


@app.route('/xhr/headphones/')
@requires_auth
def xhr_headphones():
    return xhr_headphones_artists()


@app.route('/xhr/headphones/artists/')
@requires_auth
def xhr_headphones_artists():
    logger.log('HEADPHONES :: Fetching artists list', 'INFO')
    command = 'getIndex'

    try:
        headphones = headphones_api(command)
        updates = headphones_api('getVersion')
    except Exception as e:
        return headphones_exception(e)


    artists = []

    for artist in headphones:
        if not 'Fetch failed' in artist['ArtistName']:
            try:
                artist['Percent'] = int(100 * float(artist['HaveTracks']) / float(artist['TotalTracks']))
            except:
                artist['Percent'] = 0

            if not hp_compact():
                artist['ThumbURL'] = hp_artistart(artist['ArtistID'])
            artists.append(artist)

    return render_template('headphones.html',
        headphones=True,
        artists=artists,
        updates=updates,
        compact=hp_compact(),
    )


@app.route('/xhr/headphones/artist/<artistid>/')
@requires_auth
def xhr_headphones_artist(artistid):
    logger.log('HEADPHONES :: Fetching artist', 'INFO')
    command = 'getArtist&id=%s' % artistid

    try:
        headphones = headphones_api(command)
    except Exception as e:
        return headphones_exception(e)

    if not hp_compact():
        for album in headphones['albums']:
            try:
                album['ThumbURL'] = hp_albumart(album['AlbumID'])
            except:
                pass

    return render_template('headphones-artist.html',
        albums=headphones,
        headphones=True,
        compact=hp_compact(),
    )


@app.route('/xhr/headphones/album/<albumid>/')
@requires_auth
def xhr_headphones_album(albumid):
    logger.log('HEADPHONES :: Fetching album', 'INFO')
    command = 'getAlbum&id=%s' % albumid

    try:
        headphones = headphones_api(command)
    except Exception as e:
        return headphones_exception(e)

    album = headphones['album'][0]

    try:
        album['ThumbURL'] = hp_albumart(album['AlbumID'])
    except:
        pass

    album['TotalDuration'] = 0

    for track in headphones['tracks']:
        if track['TrackDuration'] == None:
            track['TrackDuration'] = 0
        album['TotalDuration'] = album['TotalDuration'] + int(track['TrackDuration'])
        track['TrackDuration'] = convert_track_duration(track['TrackDuration'])

    album['TotalDuration'] = convert_track_duration(album['TotalDuration'])
    album['Tracks'] = len(headphones['tracks'])

    return render_template('headphones-album.html',
        album=headphones,
        headphones=True,
        compact=hp_compact(),
    )


@app.route('/xhr/headphones/upcoming/')
@requires_auth
def xhr_headphones_upcoming():
    logger.log('HEADPHONES :: Fetching upcoming albums', 'INFO')
    command = 'getUpcoming'

    try:
        headphones = headphones_api(command)
    except Exception as e:
        return headphones_exception(e)

    if headphones == []:
        headphones = 'empty'

    for album in headphones:
        try:
            album['ThumbURL'] = hp_albumart(headphones[0]['AlbumID'])
        except:
            pass

    return render_template('headphones-upcoming.html',
        upcoming=headphones,
        headphones=True,
        compact=hp_compact(),
    )


@app.route('/xhr/headphones/similar/')
@requires_auth
def xhr_headphones_similar():
    logger.log('HEADPHONES :: Fetching similar artists', 'INFO')
    command = 'getSimilar'

    try:
        headphones = headphones_api(command)
    except Exception as e:
        return headphones_exception(e)

    return render_template('headphones-similar.html',
        similar=headphones,
        headphones=True,
    )


@app.route('/xhr/headphones/search/<type>/<query>/')
@requires_auth
def xhr_headphones_search(type, query):
    if type == 'artist':
        logger.log('HEADPHONES :: Searching for artist', 'INFO')
        command = 'findArtist&name=%s' % urllib.quote(query)
    else:
        logger.log('HEADPHONES :: Searching for album', 'INFO')
        command = 'findAlbum&name=%s' % urllib.quote(query)

    try:
        headphones = headphones_api(command)
    except Exception as e:
        return headphones_exception(e)

    for artist in headphones:
        artist['url'].replace('\/', '/')

    return render_template('headphones-search_dialog.html',
        headphones=True,
        search=headphones,
        query=query
    )


@app.route('/xhr/headphones/artist/<artistid>/<action>/')
@requires_auth
def xhr_headphones_artist_action(artistid, action):
    if action == 'pause':
        logger.log('HEADPHONES :: Pausing artist', 'INFO')
        command = 'pauseArtist&id=%s' % artistid
    elif action == 'resume':
        logger.log('HEADPHONES :: Resuming artist', 'INFO')
        command = 'resumeArtist&id=%s' % artistid
    elif action == 'refresh':
        logger.log('HEADPHONES :: Refreshing artist', 'INFO')
        command = 'refreshArtist&id=%s' % artistid
    elif action == 'remove':
        logger.log('HEADPHONES :: Removing artist', 'INFO')
        command = 'delArtist&id=%s' % artistid
    elif action == 'add':
        logger.log('HEADPHONES :: Adding artist', 'INFO')
        command = 'addArtist&id=%s' % artistid

    try:
        if command == 'remove':
            headphones_api(command, False)
        elif command == 'pause':
            headphones_api(command, False)
        elif command == 'resume':
            headphones_api(command, False)
        else:
            Thread(target=headphones_api, args=(command, False)).start()
    except Exception as e:
        return headphones_exception(e)

    return jsonify(status='successful')


@app.route('/xhr/headphones/album/<albumid>/<status>/')
@requires_auth
def xhr_headphones_album_status(albumid, status):
    if status == 'wanted':
        logger.log('HEADPHONES :: Marking album as wanted', 'INFO')
        command = 'queueAlbum&id=%s' % albumid
    if status == 'wanted_new':
        logger.log('HEADPHONES :: Marking album as wanted (new)', 'INFO')
        command = 'queueAlbum&new=True&id=%s' % albumid
    if status == 'skipped':
        logger.log('HEADPHONES :: Marking album as skipped', 'INFO')
        command = 'unqueueAlbum&id=%s' % albumid

    try:
        Thread(target=headphones_api, args=(command, False)).start()
    except Exception as e:
        return headphones_exception(e)

    return jsonify(status='successful')


@app.route('/xhr/headphones/control/<command>/')
@requires_auth
def xhr_headphones_control(command):
    if command == 'shutdown':
        logger.log('HEADPHONES :: Shutting down', 'INFO')

    elif command == 'restart':
        logger.log('HEADPHONES :: Restarting', 'INFO')

    elif command == 'update':
        logger.log('HEADPHONES :: Updating', 'INFO')

    elif command == 'force_search':
        logger.log('HEADPHONES :: Forcing wanted album search', 'INFO')
        command = 'forceSearch'

    elif command == 'force_process':
        logger.log('HEADPHONES :: Forcing post process', 'INFO')
        command = 'forceProcess'

    try:
        Thread(target=headphones_api, args=(command, False)).start()
    except Exception as e:
        return headphones_exception(e)

    return jsonify(status='successful')
