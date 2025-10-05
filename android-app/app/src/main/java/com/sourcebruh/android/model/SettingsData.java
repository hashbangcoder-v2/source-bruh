package com.sourcebruh.android.model;

public class SettingsData {
    private final String email;
    private final String albumUrl;
    private final boolean geminiKeySet;

    public SettingsData(String email, String albumUrl, boolean geminiKeySet) {
        this.email = email == null ? "" : email;
        this.albumUrl = albumUrl == null ? "" : albumUrl;
        this.geminiKeySet = geminiKeySet;
    }

    public String getEmail() {
        return email;
    }

    public String getAlbumUrl() {
        return albumUrl;
    }

    public boolean isGeminiKeySet() {
        return geminiKeySet;
    }
}
