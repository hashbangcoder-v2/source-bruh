package com.sourcebruh.android.network;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import androidx.annotation.Nullable;

import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.google.firebase.auth.GetTokenResult;
import com.sourcebruh.android.R;
import com.sourcebruh.android.model.SearchResult;
import com.sourcebruh.android.model.SettingsData;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class BackendClient {
    public interface BackendCallback<T> {
        void onSuccess(T result);
        void onError(Exception e);
    }

    private static final MediaType JSON_MEDIA = MediaType.get("application/json; charset=utf-8");
    private static final ExecutorService EXECUTOR = Executors.newCachedThreadPool();
    private static final Handler MAIN_HANDLER = new Handler(Looper.getMainLooper());
    private static final OkHttpClient CLIENT = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build();

    private BackendClient() {
    }

    public static void fetchSettings(Context context, BackendCallback<SettingsData> callback) {
        HttpUrl url;
        try {
            url = resolveUrl(context, "/settings");
        } catch (IllegalArgumentException e) {
            postError(callback, e);
            return;
        }
        authorizedRequest(context, url, "GET", null, new BackendCallback<String>() {
            @Override
            public void onSuccess(String body) {
                try {
                    JSONObject json = new JSONObject(body);
                    SettingsData data = new SettingsData(
                            json.optString("email"),
                            json.optString("album_url"),
                            json.optBoolean("gemini_key_set")
                    );
                    postSuccess(callback, data);
                } catch (JSONException e) {
                    postError(callback, e);
                }
            }

            @Override
            public void onError(Exception e) {
                postError(callback, e);
            }
        });
    }

    public static void updateGeminiKey(Context context, String apiKey, BackendCallback<Void> callback) {
        HttpUrl url;
        try {
            url = resolveUrl(context, "/settings/gemini-key");
        } catch (IllegalArgumentException e) {
            postError(callback, e);
            return;
        }
        JSONObject body = new JSONObject();
        try {
            body.put("api_key", apiKey);
        } catch (JSONException e) {
            postError(callback, e);
            return;
        }
        authorizedRequest(context, url, "POST", body, new BackendCallback<String>() {
            @Override
            public void onSuccess(String result) {
                postSuccess(callback, null);
            }

            @Override
            public void onError(Exception e) {
                postError(callback, e);
            }
        });
    }

    public static void updateAlbumUrl(Context context, String albumUrl, BackendCallback<String> callback) {
        HttpUrl url;
        try {
            url = resolveUrl(context, "/settings/album-url");
        } catch (IllegalArgumentException e) {
            postError(callback, e);
            return;
        }
        JSONObject body = new JSONObject();
        try {
            body.put("album_url", albumUrl == null ? "" : albumUrl);
        } catch (JSONException e) {
            postError(callback, e);
            return;
        }
        authorizedRequest(context, url, "POST", body, new BackendCallback<String>() {
            @Override
            public void onSuccess(String result) {
                try {
                    JSONObject json = new JSONObject(result);
                    String normalized = json.optString("album_url");
                    postSuccess(callback, normalized);
                } catch (JSONException e) {
                    postError(callback, e);
                }
            }

            @Override
            public void onError(Exception e) {
                postError(callback, e);
            }
        });
    }

    public static void search(Context context, String query, int topK, BackendCallback<List<SearchResult>> callback) {
        HttpUrl base;
        try {
            base = resolveUrl(context, "/search");
        } catch (IllegalArgumentException e) {
            postError(callback, e);
            return;
        }
        HttpUrl url = base.newBuilder()
                .addQueryParameter("q", query)
                .addQueryParameter("top_k", String.valueOf(topK))
                .build();
        authorizedRequest(context, url, "GET", null, new BackendCallback<String>() {
            @Override
            public void onSuccess(String body) {
                try {
                    JSONArray array = new JSONArray(body);
                    List<SearchResult> results = new ArrayList<>();
                    for (int i = 0; i < array.length(); i++) {
                        JSONObject item = array.getJSONObject(i);
                        results.add(new SearchResult(
                                item.optString("image_rowid"),
                                item.optDouble("distance"),
                                item.optString("description"),
                                item.optString("album_title"),
                                item.optString("timestamp"),
                                item.optString("thumb_url")
                        ));
                    }
                    postSuccess(callback, results);
                } catch (JSONException e) {
                    postError(callback, e);
                }
            }

            @Override
            public void onError(Exception e) {
                postError(callback, e);
            }
        });
    }

    public static void addImageFromUrl(Context context, String imageUrl, @Nullable String pageUrl,
                                       BackendCallback<Void> callback) {
        HttpUrl url;
        try {
            url = resolveUrl(context, "/images/from-url");
        } catch (IllegalArgumentException e) {
            postError(callback, e);
            return;
        }
        JSONObject body = new JSONObject();
        try {
            body.put("image_url", imageUrl);
            if (pageUrl != null) {
                body.put("page_url", pageUrl);
            }
        } catch (JSONException e) {
            postError(callback, e);
            return;
        }
        authorizedRequest(context, url, "POST", body, new BackendCallback<String>() {
            @Override
            public void onSuccess(String result) {
                postSuccess(callback, null);
            }

            @Override
            public void onError(Exception e) {
                postError(callback, e);
            }
        });
    }

    public static void logout(Context context) {
        HttpUrl url;
        try {
            url = resolveUrl(context, "/settings/logout");
        } catch (IllegalArgumentException e) {
            return;
        }
        authorizedRequest(context, url, "POST", new JSONObject(), new BackendCallback<String>() {
            @Override
            public void onSuccess(String result) {
                // no-op
            }

            @Override
            public void onError(Exception e) {
                // ignore logout errors
            }
        });
    }

    private static void authorizedRequest(Context context, HttpUrl url, String method, @Nullable JSONObject body,
                                          BackendCallback<String> callback) {
        FirebaseUser user = FirebaseAuth.getInstance().getCurrentUser();
        if (user == null) {
            postError(callback, new IllegalStateException("User not signed in"));
            return;
        }
        user.getIdToken(true).addOnCompleteListener(task -> {
            if (!task.isSuccessful()) {
                postError(callback, task.getException() != null ? task.getException() :
                        new IllegalStateException("Failed to get auth token"));
                return;
            }
            GetTokenResult result = task.getResult();
            if (result == null || result.getToken() == null) {
                postError(callback, new IllegalStateException("Missing auth token"));
                return;
            }
            String token = result.getToken();
            EXECUTOR.execute(() -> {
                Request.Builder builder = new Request.Builder()
                        .url(url)
                        .addHeader("Authorization", "Bearer " + token);
                if ("GET".equalsIgnoreCase(method)) {
                    builder.get();
                } else {
                    RequestBody requestBody = RequestBody.create(body != null ? body.toString() : "{}", JSON_MEDIA);
                    builder.method(method, requestBody);
                    builder.addHeader("Content-Type", "application/json");
                }

                try (Response response = CLIENT.newCall(builder.build()).execute()) {
                    int code = response.code();
                    String responseBody = response.body() != null ? response.body().string() : "";
                    if (code >= 200 && code < 300) {
                        postSuccess(callback, responseBody != null ? responseBody : "");
                    } else {
                        String message = extractErrorMessage(responseBody, code);
                        postError(callback, new IOException(message));
                    }
                } catch (IOException e) {
                    postError(callback, e);
                }
            });
        });
    }

    private static HttpUrl resolveUrl(Context context, String path) {
        String base = context.getString(R.string.backend_base_url);
        String cleanBase = base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
        String cleanPath = path.startsWith("/") ? path.substring(1) : path;
        HttpUrl url = HttpUrl.parse(cleanBase + "/" + cleanPath);
        if (url == null) {
            throw new IllegalArgumentException("Invalid backend URL");
        }
        return url;
    }

    private static void postSuccess(BackendCallback<?> callback, Object value) {
        MAIN_HANDLER.post(() -> {
            @SuppressWarnings("unchecked")
            BackendCallback<Object> cast = (BackendCallback<Object>) callback;
            cast.onSuccess(value);
        });
    }

    private static void postError(BackendCallback<?> callback, Exception error) {
        MAIN_HANDLER.post(() -> {
            @SuppressWarnings("unchecked")
            BackendCallback<Object> cast = (BackendCallback<Object>) callback;
            cast.onError(error);
        });
    }

    private static String extractErrorMessage(String body, int code) {
        if (body == null || body.isEmpty()) {
            return "Request failed with status " + code;
        }
        try {
            JSONObject json = new JSONObject(body);
            if (json.has("detail")) {
                return json.getString("detail");
            }
        } catch (JSONException ignored) {
        }
        return body;
    }
}
