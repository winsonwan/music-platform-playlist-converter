import time
start_time = time.time()
import spotipy
import urllib
import logging
import requests
import os
os.system("")

from SpotifyConverterClass import SpotifyConverter
from YouTubeConverterClass import YouTubeMusicConverter
from spotipy.oauth2 import SpotifyOAuth
from spotipy.oauth2 import SpotifyClientCredentials
from ytmusicapi import YTMusic
from termcolor import colored
from dotenv import load_dotenv, dotenv_values
load_dotenv()

''' YTM_CLIENT: unofficial YouTube Music API (ytmusicapi library) client '''
# YTMusic.setup('headers_auth.json')
YTM_CLIENT = YTMusic('headers_auth.json')

''' SP_CLIENT: authorization code flow'''
SP_SCOPE = "playlist-read-private playlist-modify-private user-library-read user-library-modify"
SP_AUTH_MANAGER = SpotifyOAuth(scope=SP_SCOPE)
SP_AUTH_URL = "https://accounts.spotify.com/api/token"
SP_AUTH_DATA = {
    'grant_type': 'client_credentials',
    'client_id': dotenv_values("SPOTIPY_CLIENT_ID"),
    'client_secret': dotenv_values("SPOTIPY_REDIRECT_URI"),
}
SP_AUTH_RESPONSE = requests.post(SP_AUTH_URL, data=SP_AUTH_DATA)
SP_AUTH_TOKEN = SP_AUTH_RESPONSE.json().get("access_token")
print("SP_AUTH_TOKEN = ", SP_AUTH_TOKEN)
SP_CLIENT = spotipy.Spotify(SP_AUTH_TOKEN)

# TODO:
# 1. fix authorization for Spotify
# 2. fix authorization for YouTube Music (use Google API instead of unofficial ytmusicapi)
# 3. create web app for easier input handling -> host on github pages
# 4. use acr cloud api to handle song matching
# 4. [MOSTLY DONE] improve find_best_match() algorithm for matching search results with query:
#    - for video results, search only the video title (instead of simply skipping and not adding)

def main():
    logging.basicConfig(
        filename="log.log", 
        level=logging.INFO,
        format=u"%(message)s",
        filemode="w",
        encoding="utf-8")
    check_exit = False
    while not check_exit:
        job = get_job()
        keep_dupes = get_keep_dupes_bool()
        if job == "Playlist":
            parsed_URL = get_playlist_URL()
            netloc = parsed_URL.netloc
            path = parsed_URL.path
            query = parsed_URL.query
            if netloc == "open.spotify.com" and path[:10] == "/playlist/":
                sp_playlist_ID = path[10:]
                do_playlist_spotify(sp_playlist_ID, keep_dupes)
            elif netloc == "music.youtube.com" and path == "/playlist":
                yt_playlist_ID = query[5:]
                do_playlist_youtube(yt_playlist_ID, keep_dupes)
        elif job == "Library":
            source = get_source()
            if source == "Spotify":
                do_library_spotify(keep_dupes)
            elif source == "YouTube Music":
                do_library_youtube(keep_dupes)
        check_exit = prompt_exit()
    get_run_time()
    return

'''
Helper functions: Utils
'''
def get_run_time() -> None:
    minutes = int((time.time() - start_time) // 60)
    seconds = int((time.time() - start_time) % 60)
    print(f"\nProgram run time: {minutes} minutes and {seconds} seconds")
    logging.info(f"\nProgram run time: {minutes} minutes and {seconds} seconds")
    return

def get_job() -> None:
    job = input(colored("\nHello! Welcome to the Spotify-Youtube playlist coverter.\n\n" 
        + "Type 'L' to convert a library, or type 'P' to convert a playlist.\n\n", "green")).upper()
    while job != "L" and job != "P":
        job = input(colored("\nERROR: Make sure you're entering either 'L' or 'P'.\n\n", "green")).upper()
    job = "Playlist" if job == "P" else "Library"
    return job

def get_keep_dupes_bool() -> None:
    keep_dupes = input(colored("\nShould we keep duplicates? " 
        + "Type 'Y' for yes, or 'N' for no.\n\n", "green")).upper()
    while keep_dupes != "Y" and keep_dupes != "N":
        keep_dupes = input(colored("\nERROR: Make sure you're entering either 'Y' or 'N'.\n\n", "green")).upper()
    keep_dupes = True if keep_dupes == "Y" else False
    return keep_dupes

def get_yt_download_bool() -> None:
    download = input(colored(f"\nShould we download the mp3 for YouTube Music videos and songs " 
        + "that we can't find on Spotify? Type 'Y' for yes, or 'N' for no.\n\n", "green")).upper()
    while download != 'Y' and download != 'N':
        download = input(colored("\nERROR: Make sure you're entering either 'Y' or 'N'.\n\n", "green")).upper()
    download = True if download.upper() == 'Y' else False
    return download

def get_source() -> None:
    source = input(colored(f"\nType 'S' if the original library is in Spotify or " 
        + "type 'Y' if the original library is in YouTube Music.\n\n", "green")).upper()
    while source.upper() != "S" and source.upper() != "Y":
        source = input(colored("\nERROR: Make sure you're entering either 'S' or 'Y'.\n\n", "green")).upper()
    source = "Spotify" if source.upper() == "S" else "YouTube Music"
    return source

def get_playlist_URL() -> None:
    input_URL = input(colored(f"\nCopy-and-paste the URL for the source playlist.\n\n", "green"))
    parsed_URL = urllib.parse.urlparse(input_URL)
    while parsed_URL.netloc != "open.spotify.com" and parsed_URL.netloc != "music.youtube.com":
        input_URL = input(colored("\nERROR: Make sure the URL leads to either a Spotify playlist or YouTube Music playlist.\n\n", "green"))
        parsed_URL= urllib.parse.urlparse(input_URL)
    return parsed_URL

def prompt_exit() -> None:
    check_exit = input(colored(f"\nType 'exit' to exit, or 'again' to convert something else.\n\n", "green"))
    while check_exit != "exit" and check_exit != "again":
        check_exit = input(colored(f"\nERROR: Make sure you're entering either 'exit' or 'again'.\n\n", "green"))
    check_exit = True if check_exit == "exit" else False
    return check_exit

'''
Convert playlist
'''
def do_playlist_spotify(sp_playlist_ID: str, keep_dupes: bool) -> None:
    sp_converter = SpotifyConverter(YTM_CLIENT, SP_CLIENT, keep_dupes)
    sp_converter.convert_SP_to_YT_playlist(sp_playlist_ID)
    sp_converter.print_not_added_songs()
    return

def do_playlist_youtube(yt_playlist_ID: str, keep_dupes: bool) -> None:
    download = get_yt_download_bool()
    yt_converter = YouTubeMusicConverter(YTM_CLIENT, SP_CLIENT, keep_dupes, download)
    yt_converter.convert_YT_to_SP_playlist(yt_playlist_ID)
    yt_converter.print_not_added_songs()
    yt_converter.download_YT_videos()
    return

'''
Convert library
'''
def do_library_spotify(keep_dupes: bool) -> None:
    sp_converter = SpotifyConverter(YTM_CLIENT, SP_CLIENT, keep_dupes)
    sp_converter.convert_SP_to_YT_library()
    return

def do_library_youtube(keep_dupes: bool) -> None:
    download = get_yt_download_bool()
    yt_converter = YouTubeMusicConverter(YTM_CLIENT, SP_CLIENT, keep_dupes, download)
    yt_converter.convert_YT_to_SP_library()
    return

if __name__ == '__main__':
    main()
    