package com.sourcebruh.android.model;

import android.os.Parcel;
import android.os.Parcelable;

public class SearchResult implements Parcelable {
    private final String imageRowId;
    private final double distance;
    private final String description;
    private final String albumTitle;
    private final String timestamp;
    private final String thumbUrl;

    public SearchResult(String imageRowId, double distance, String description,
                        String albumTitle, String timestamp, String thumbUrl) {
        this.imageRowId = imageRowId;
        this.distance = distance;
        this.description = description;
        this.albumTitle = albumTitle;
        this.timestamp = timestamp;
        this.thumbUrl = thumbUrl;
    }

    protected SearchResult(Parcel in) {
        imageRowId = in.readString();
        distance = in.readDouble();
        description = in.readString();
        albumTitle = in.readString();
        timestamp = in.readString();
        thumbUrl = in.readString();
    }

    public static final Creator<SearchResult> CREATOR = new Creator<SearchResult>() {
        @Override
        public SearchResult createFromParcel(Parcel in) {
            return new SearchResult(in);
        }

        @Override
        public SearchResult[] newArray(int size) {
            return new SearchResult[size];
        }
    };

    public String getImageRowId() {
        return imageRowId;
    }

    public double getDistance() {
        return distance;
    }

    public String getDescription() {
        return description;
    }

    public String getAlbumTitle() {
        return albumTitle;
    }

    public String getTimestamp() {
        return timestamp;
    }

    public String getThumbUrl() {
        return thumbUrl;
    }

    @Override
    public int describeContents() {
        return 0;
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeString(imageRowId);
        dest.writeDouble(distance);
        dest.writeString(description);
        dest.writeString(albumTitle);
        dest.writeString(timestamp);
        dest.writeString(thumbUrl);
    }
}
