import math
import spotipy

from termcolor import colored
from spotipy.oauth2 import SpotifyOAuth

class YouTubeMusicConverter():
    ''' SCORE_COEFFICIENT: constant by which we linearly increment scores when scoring YT search results '''
    SCORE_COEFFICIENT = 100

    ''' EXP_COEFFICIENT: constant by which we exponentially punish differences in song duration when 
    scoring YT search results (eg. score -= e^(EXP_COEFFICIENT*(abs(DIFFERENCE_IN_SONG_DURATION))))
    '''
    EXP_COEFFICIENT = 0.5

    ''' NOT_ADDED_SONGS: dict where (str) keys = playlist names -> (dict) values = {"unfound":[str], "dupes":[str]}
    - NOT_ADDED_SONGS -> {str:{"unfounded":[str], "dupes":[str]})}
        - "unfound" -> (list) list of song YT queries that were not added because they could not be found
        - "dupes" -> (list) list of song YT queries that were not added because they were duplicates
    '''
    NOT_ADDED_SONGS = {}

    ''' NOT_ADDED_ALBUMS: list of album names that were not added because they could not be found'''
    NOT_ADDED_ALBUMS = []

    def __init__(self, YTM_CLIENT, KEEP_DUPES) -> None:
        self.ytm_client = YTM_CLIENT
        self.keep_dupes = KEEP_DUPES
        pass

    def convert_YT_to_SP_library(self) -> None:
        '''
        Converts current user's YouTube Music library (liked songs, liked albums, all playlists) to 
        Spotify. In order: Liked songs -> Playlists -> Albums\n
        Parameters:
        - None
        Return:
        - None
        '''
        # Convert YouTube Music Liked Videos and all playlists to YouTube Music playlist
        sp_scope = "playlist-modify-private"
        sp_client = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=sp_scope))
        for yt_playlist in self.ytm_client.get_library_playlists(limit=None):
            yt_playlist_ID = yt_playlist["playlistId"]
            self.convert_YT_to_SP_playlist(sp_client, yt_playlist_ID)

        # Convert YouTube Music Liked Albums to Spotify Liked Albums
        sp_scope = "user-library-modify"
        sp_client = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=sp_scope))
        liked_albums = self.ytm_client.get_library_albums(limit=None)
        self.convert_YT_liked_albums(sp_client, liked_albums)

        # Print unadded songs from each playlist
        self.print_not_added_songs()

        # Print unadded Spotify albums
        self.print_not_added_albums()
        return 

    def convert_YT_to_SP_playlist(self, sp_client: spotipy.client, yt_playlist_ID: str) -> str:
        '''
        Converts YouTube Music playlist with given playlist ID to Spotify playlist.\n
        Parameters:
        - (spotipy.client) sp_client: Spotify API client
        - (str) yt_playlist_ID: playlist ID for source YouTube Music playlist\n
        Return:
        - (str) playlist ID for newly created Spotify playlist
        '''
        if yt_playlist_ID == "LIKED_SONGS":
            yt_playlist_name = "Liked Songs"
            yt_playlist = self.ytm_client.get_library_songs(limit=None)
        elif yt_playlist_ID == "LIKED_VIDS":
            yt_playlist_name = "Liked Videos"
            yt_playlist = self.ytm_client.get_liked_songs(limit=None)
        else:
            yt_playlist_name = self.ytm_client.get_playlist(yt_playlist_ID)["title"]
            yt_playlist = self.ytm_client.get_playlist(yt_playlist_ID, limit=None)
        print(colored(f"\nYouTube Music playlist detected: '{yt_playlist_name}'", "green"))
        yt_tracks = yt_playlist["tracks"]
        sp_playlist = {}
        count = 1
        print(colored("Copying contents into Spotify playlist...", "green"))
        for yt_song in yt_tracks:
            try:
                song_info = self.get_YT_song_info(yt_song)
                full_sp_query = f"{song_info['name']} by {song_info['artist']}"
                if yt_song["videoType"] == "MUSIC_VIDEO_TYPE_ATV":
                    sp_query = f"{song_info['name']} {song_info['artist']}"
                else:
                    sp_query = f"{song_info['name']}"
                sp_search_res = sp_client.search(sp_query, type="track", limit=50)["tracks"]["items"]
                try:
                    best_match_ID = self.find_best_match(sp_search_res, song_info)
                    if best_match_ID not in sp_playlist:
                        sp_playlist[best_match_ID] = {"full_sp_query": full_sp_query, "count":1}
                    else:
                        sp_playlist[best_match_ID]["count"] += 1
                    print(colored(f"Copying song {count}/{len(yt_tracks)}", "green"))
                except ValueError:
                    if yt_playlist_name not in self.NOT_ADDED_SONGS:
                        self.NOT_ADDED_SONGS[yt_playlist_name] = {"unfound":[], "dupes":[]}
                    self.NOT_ADDED_SONGS[yt_playlist_name]["unfound"].append(full_sp_query)
                    print(f"ERROR: '{full_sp_query}' not found.")
            except TypeError:
                print(f"ERROR: Song #{count} in Spotify playlist '{yt_playlist_name}' could not be found " 
                    + f"(It was {type(yt_song)} type. Not a song dict).")
            count += 1
        sp_playlist_ID = self.create_SP_playlist(sp_client, yt_playlist_name, sp_playlist)
        return sp_playlist_ID

    def convert_YT_liked_albums(self, sp_client, liked_albums) -> None:
        if liked_albums:
            print(colored(f"\nAdding YouTube Music saved albums to Spotify library...", "green"))
            for album in liked_albums:
                found = {}
                album_name = album["title"]
                album_artist = album["artists"][0]["name"]
                album_year = album["year"]
                sp_query = f"{album_name} by {album_artist}"
                sp_search_res = sp_client.search(sp_query, type="album")["albums"]["items"]
                for res in sp_search_res:
                    res_ID = res["id"]
                    found[res_ID] = 0
                    if res['artists'][0]['name'] == album_artist:
                        found[res_ID] += self.SCORE_COEFFICIENT
                    if res['name'] == album_name:
                        found[res_ID] += self.SCORE_COEFFICIENT
                    if res['name'] in album_name or album_name in res['name']:
                        found[res_ID] += self.SCORE_COEFFICIENT
                    if res['release_date'][:3] == album_year:
                        found[res_ID] += self.SCORE_COEFFICIENT
                try:
                    sp_client.current_user_saved_albums_add([max(found, key=found.get)])
                    print(colored(f"Added album: {sp_query}", "green"))
                except ValueError:
                    self.NOT_ADDED_ALBUMS.append(sp_query)
        return

    def find_best_match(self, sp_search_res: list, song_info: dict) -> str:
        '''
        Given a list of Spotify search results and a target song to match, holistically score each 
        search result and then return the result with the highest score (ie. the best match).\n
        Parameters:
        - (list) sp_search_res: list of Spotify search results
        - (dict) song_info: dictionary with song name, artist, album and duration\n
        Return
        - (str) song ID of search result with best holistic score (ie. best match to the song in song_info)
        '''
        found = {}
        while sp_search_res:
            res = sp_search_res.pop(0)
            found[res["id"]] = 0
            res_title = res["name"].lower()
            res_artist = res["artists"][0]["name"].lower()
            res_album = res["album"]["name"].lower()
            res_duration = res["duration_ms"]/1000
            # Prefer results with the exact same name as Spotify song title
            if song_info["name"] == res_title and song_info["artist"] == res_artist:
                found[res["id"]] += float('inf')
                break
            # Prefer results from the same album as on Spotify
            if res_album and res_album == song_info["album"]:
                found[res["id"]] += self.SCORE_COEFFICIENT
            # Exponentially punish differences in song duration
            try:
                found[res["id"]] -= math.exp(self.EXP_COEFFICIENT*abs(song_info["duration_seconds"]-res_duration))
            except OverflowError:
                found[res["id"]] = float("-inf")
        try:
            best_match_ID = max(found, key = found.get)
            return best_match_ID
        except ValueError:
            return None

    def create_SP_playlist(self, sp_client: spotipy.client, yt_playlist_name: str, sp_playlist: dict) -> str:    
        '''
        Creates a Spotify playlist and handles duplicates based on self.keep_dupes.\n
        Parameters:
        - (spotipy.client) SP_CLIENT: Spotify API client
        - (str) YT_PLAYLIST_NAME: name of Spotify playlist
        - (dict) SP_PLAYLIST: 
            - keys: (str) song IDs | values: (dict) {"full_sp_query":str, "count":int}
                - full_sp_query = f"{song['name']} by {song['artist']}"
                - count = number of times the given song ID has been added (eg. duplicate songs)\n
        Return:
        - (str) playlist ID of newly created Spotify playlist
        '''
        print(colored("Finishing up...", "green"))

        # CREATE SPOTIFY PLAYLIST
        user_ID = sp_client.me()["id"]
        sp_playlist_ID = sp_client.user_playlist_create(
                        user=user_ID, 
                        name=f"{yt_playlist_name} (copied from YouTube Music)",
                        public=False,
                        collaborative=False,
                        description="Includes duplicates" if self.keep_dupes else "Does not include duplicates")["id"]

        # ADD LIST OF SONGS TO SPOTIFY PLAYLIST
        add_songs = list(sp_playlist.keys())
        while len(add_songs) > 100:
            sp_client.user_playlist_add_tracks(user_ID, sp_playlist_ID, add_songs[:100])
            add_songs = add_songs[100:]
        sp_client.user_playlist_add_tracks(user_ID, sp_playlist_ID, add_songs)

        # HANDLE DUPLICATES
        dupes = []
        for song_ID in sp_playlist:
            count = sp_playlist[song_ID]["count"]
            if count > 1:
                for _ in range(count-1):
                    dupes.append(song_ID)
                    if not self.keep_dupes:
                        self.NOT_ADDED_SONGS[yt_playlist_name]["dupes"].append(sp_playlist[song_ID]['sp_query'])
        if self.keep_dupes and dupes:
            while len(add_songs) > 100:
                sp_client.user_playlist_add_tracks(user_ID, sp_playlist_ID, dupes[:100])
                dupes = dupes[100:]
            sp_client.user_playlist_add_tracks(user_ID, sp_playlist_ID, dupes)

        print(colored("Finished! Spotify playlist has been created.\n" 
                    + "Check your Spotify library to find it.", "green"))
        return sp_playlist_ID

    def get_YT_song_info(self, song: dict) -> dict:
        '''
        Given a YouTube Music song, summarize important song information into a dictionary\n
        Parameters:
        - (dict) song: YouTube Music song dictionary\n
        Return:
        - (dict) dictionary with song name, artist, album, and duration
        '''
        song_info = {}
        song_info["name"] = song["title"].lower()
        song_info["artist"] = song["artists"][0]["name"].lower()
        if song["album"] != None:
            song_info["album"] = song["album"]["name"]
        else:
            song_info["album"] = None
        song_duration_raw = song["duration"]
        song_info["duration_seconds"] = self.get_sec_from_raw_duration(song_duration_raw)
        return song_info

    def get_sec_from_raw_duration(self, song_duration_raw: str) -> int:
        '''
        Converts a time string in "hour:minute:second" format to total seconds.\n
        Parameters:
        - (str) song_duration_raw: a string representing a time duration in "hour:minute:second" format\n
        Return:
        - (int) song_duration_raw in seconds
        '''
        tokens = song_duration_raw.split(":")
        tokens = [int(i) for i in tokens]
        song_duration_sec = sum([i*(60**(len(tokens)-tokens.index(i)-1)) for i in tokens])
        return song_duration_sec

    def print_not_added_songs(self) -> None:
        '''
        Prints all songs queries that were not added, either because they could not 
        be found or because they are duplicates, using global variable NOT_ADDED.\n
        Parameters:
        - None\n
        Return:
        - None
        '''
        if self.NOT_ADDED_SONGS:
            print(colored("\nThe following songs could not be found and were not added:\n", "green"))
            index = 1
            for playlist in self.NOT_ADDED_SONGS:
                print(f"-----PLAYLIST: {playlist}-----")
                for song_query in self.NOT_ADDED_SONGS[playlist]["unfound"]:
                    print(f"{index}. {song_query}")
                    index += 1
            if index == 1:
                print("None. All songs were fuound.")
            if not self.keep_dupes:
                print(colored("\nThe following songs were duplicates and were not added:\n", "green"))
                index = 1
                for playlist in self.NOT_ADDED_SONGS:
                    print(f"-----PLAYLIST: {playlist}-----")
                    for song_query in self.NOT_ADDED_SONGS[playlist]["dupes"]:
                        print(f"{index}. {song_query}")
                        index += 1
                if index == 1:
                    print("None. Source playlist had no duplicates.")
        return

    def print_not_added_albums(self) -> None:
        if self.NOT_ADDED_ALBUMS:
            print("\nThe following albums could not be found and were not added:")
            for index, album in enumerate(self.NOT_ADDED_ALBUMS):
                print(f"{index + 1}. {album}")
        return