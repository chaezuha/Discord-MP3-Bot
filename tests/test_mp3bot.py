import os
import time
from pathlib import Path

import pytest

import mp3bot
from mp3bot import Song, get_catalog, normalize_text, score_song, search_songs


@pytest.fixture(autouse=True)
def reset_catalog_cache():
    mp3bot._catalog_cache = None
    yield
    mp3bot._catalog_cache = None


def make_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, titles: list[str]) -> Path:
    for title in titles:
        (tmp_path / f"{title}.mp3").write_bytes(b"")
    monkeypatch.setattr(mp3bot, "DISCORD_MUSIC_PATH", tmp_path)
    return tmp_path


class TestNormalizeText:
    def test_lowercases(self):
        assert normalize_text("Hello World") == "hello world"

    def test_strips_punctuation(self):
        assert normalize_text("AC/DC - Back in Black!") == "ac dc back in black"

    def test_collapses_whitespace(self):
        assert normalize_text("  too   many\tspaces  ") == "too many spaces"

    def test_empty(self):
        assert normalize_text("") == ""
        assert normalize_text("!!!") == ""


class TestScoreSong:
    def test_exact_match_scores_100(self):
        song = Song(path=Path("a.mp3"), title="Bohemian Rhapsody")
        assert score_song(song, "bohemian rhapsody") == 100

    def test_prefix_match_scores_95(self):
        song = Song(path=Path("a.mp3"), title="Bohemian Rhapsody")
        assert score_song(song, "bohemian") == 95

    def test_substring_match_scores_88(self):
        song = Song(path=Path("a.mp3"), title="Bohemian Rhapsody")
        assert score_song(song, "rhapsody") == 88

    def test_token_subset_gets_bonus_capped_at_99(self):
        song = Song(path=Path("a.mp3"), title="The Quick Brown Fox Jumps")
        score = score_song(song, "fox brown")
        assert score <= 99
        assert score > score_song(song, "fox purple")

    def test_unrelated_query_scores_low(self):
        song = Song(path=Path("a.mp3"), title="Bohemian Rhapsody")
        assert score_song(song, "zzzz qqqq") < 35


class TestGetCatalog:
    def test_missing_path_returns_empty(self, monkeypatch):
        monkeypatch.setattr(mp3bot, "DISCORD_MUSIC_PATH", None)
        assert get_catalog() == []

    def test_nonexistent_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mp3bot, "DISCORD_MUSIC_PATH", tmp_path / "nope")
        assert get_catalog() == []

    def test_lists_mp3s_sorted_case_insensitively(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, ["beta", "Alpha", "gamma"])
        (tmp_path / "notes.txt").write_text("not a song")
        catalog = get_catalog()
        assert [song.title for song in catalog] == ["Alpha", "beta", "gamma"]

    def test_cache_refreshes_when_folder_mtime_changes(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, ["one"])
        assert len(get_catalog()) == 1

        (tmp_path / "two.mp3").write_bytes(b"")
        # Bump the folder mtime explicitly: some filesystems have coarse
        # timestamps, so a fast consecutive write may not change it on its own.
        future = time.time() + 10
        os.utime(tmp_path, (future, future))
        assert len(get_catalog()) == 2

    def test_cache_hit_when_mtime_unchanged(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, ["one"])
        first = get_catalog()
        assert get_catalog() is first


class TestSearchSongs:
    def test_empty_catalog_returns_empty(self, monkeypatch):
        monkeypatch.setattr(mp3bot, "DISCORD_MUSIC_PATH", None)
        assert search_songs("anything") == []

    def test_exact_match_ranks_first(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, ["Yellow Submarine", "Yellow", "Mellow Yellow"])
        results = search_songs("yellow")
        assert results[0][0].title == "Yellow"
        assert results[0][1] == 100

    def test_filters_out_low_scores(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, ["Bohemian Rhapsody", "Stairway to Heaven"])
        titles = [song.title for song, _ in search_songs("bohemian")]
        assert titles == ["Bohemian Rhapsody"]

    def test_limit_is_respected(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, [f"song {index}" for index in range(20)])
        assert len(search_songs("song", limit=5)) == 5

    def test_blank_query_returns_catalog_head(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, ["b", "a", "c"])
        results = search_songs("   ", limit=2)
        assert [song.title for song, _ in results] == ["a", "b"]
        assert all(score == 0 for _, score in results)

    def test_ties_break_alphabetically(self, tmp_path, monkeypatch):
        make_library(tmp_path, monkeypatch, ["Remix B", "Remix A"])
        results = search_songs("remix")
        assert [song.title for song, _ in results] == ["Remix A", "Remix B"]
