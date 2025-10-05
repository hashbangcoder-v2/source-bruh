package com.sourcebruh.android;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.ImageButton;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.sourcebruh.android.model.SettingsData;
import com.sourcebruh.android.network.BackendClient;

public class SettingsActivity extends AppCompatActivity {

    private TextInputEditText apiKeyInput;
    private TextInputEditText sourcesInput;
    private TextView apiKeyStatus;
    private TextView settingsStatus;
    private TextView userName;
    private TextView userEmail;
    private MaterialButton apiKeyAction;
    private MaterialButton saveSourcesButton;
    private MaterialButton signOutButton;
    private SettingsData settingsData;
    private boolean editingApiKey = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        apiKeyInput = findViewById(R.id.api_key);
        sourcesInput = findViewById(R.id.sources);
        apiKeyStatus = findViewById(R.id.api_key_status);
        settingsStatus = findViewById(R.id.settings_status);
        userName = findViewById(R.id.user_name);
        userEmail = findViewById(R.id.user_email);
        apiKeyAction = findViewById(R.id.api_key_action);
        saveSourcesButton = findViewById(R.id.save_sources);
        signOutButton = findViewById(R.id.sign_out);
        ImageButton backButton = findViewById(R.id.back_button);

        backButton.setOnClickListener(v -> finish());

        apiKeyAction.setOnClickListener(v -> handleApiKeyAction());
        saveSourcesButton.setOnClickListener(v -> saveSources());
        signOutButton.setOnClickListener(v -> signOut());
    }

    @Override
    protected void onResume() {
        super.onResume();
        ensureAuthenticated();
        loadSettings();
    }

    private void ensureAuthenticated() {
        FirebaseUser user = FirebaseAuth.getInstance().getCurrentUser();
        if (user == null) {
            startActivity(new Intent(this, LoginActivity.class));
            finish();
        } else {
            String displayName = !TextUtils.isEmpty(user.getDisplayName()) ? user.getDisplayName() : user.getEmail();
            userName.setText(displayName != null ? displayName : "");
            userEmail.setText(user.getEmail() != null ? user.getEmail() : "");
        }
    }

    private void loadSettings() {
        setWorking(true);
        settingsStatus.setText("");
        BackendClient.fetchSettings(this, new BackendClient.BackendCallback<SettingsData>() {
            @Override
            public void onSuccess(SettingsData result) {
                setWorking(false);
                settingsData = result;
                renderSettings();
            }

            @Override
            public void onError(Exception e) {
                setWorking(false);
                settingsStatus.setText(e.getMessage());
                if (e.getMessage() != null && e.getMessage().toLowerCase().contains("invalid")) {
                    signOut();
                }
            }
        });
    }

    private void renderSettings() {
        editingApiKey = editingApiKey && (settingsData != null && !settingsData.isGeminiKeySet());
        boolean keySet = settingsData != null && settingsData.isGeminiKeySet();
        apiKeyStatus.setText(keySet ? getString(R.string.settings_api_key_configured)
                : getString(R.string.settings_api_key_not_configured));
        apiKeyInput.setText(keySet && !editingApiKey ? "••••••••••" : "");
        apiKeyInput.setEnabled(editingApiKey || !keySet);
        apiKeyAction.setText(editingApiKey || !keySet ? getString(R.string.settings_update) : getString(R.string.settings_edit));
        if (settingsData != null) {
            sourcesInput.setText(settingsData.getAlbumUrl());
            if (!TextUtils.isEmpty(settingsData.getEmail()) && (userEmail.getText() == null || TextUtils.isEmpty(userEmail.getText()))) {
                userEmail.setText(settingsData.getEmail());
            }
        }
        settingsStatus.setText("");
    }

    private void handleApiKeyAction() {
        boolean keySet = settingsData != null && settingsData.isGeminiKeySet();
        if (!editingApiKey && keySet) {
            editingApiKey = true;
            apiKeyInput.setText("");
            apiKeyInput.setEnabled(true);
            apiKeyInput.requestFocus();
            apiKeyAction.setText(R.string.settings_update);
            return;
        }

        String apiKey = apiKeyInput.getText() != null ? apiKeyInput.getText().toString().trim() : "";
        if (TextUtils.isEmpty(apiKey)) {
            Toast.makeText(this, R.string.error_api_key_required, Toast.LENGTH_SHORT).show();
            return;
        }
        setWorking(true);
        settingsStatus.setText(R.string.settings_status_saving);
        BackendClient.updateGeminiKey(this, apiKey, new BackendClient.BackendCallback<Void>() {
            @Override
            public void onSuccess(Void result) {
                setWorking(false);
                editingApiKey = false;
                settingsStatus.setText(R.string.settings_status_saved);
                loadSettings();
            }

            @Override
            public void onError(Exception e) {
                setWorking(false);
                settingsStatus.setText(e.getMessage());
            }
        });
    }

    private void saveSources() {
        String album = sourcesInput.getText() != null ? sourcesInput.getText().toString().trim() : "";
        setWorking(true);
        settingsStatus.setText(R.string.settings_status_saving);
        BackendClient.updateAlbumUrl(this, album, new BackendClient.BackendCallback<String>() {
            @Override
            public void onSuccess(String result) {
                setWorking(false);
                settingsStatus.setText(R.string.settings_status_saved);
                if (settingsData != null) {
                    settingsData = new SettingsData(settingsData.getEmail(), result, settingsData.isGeminiKeySet());
                }
                sourcesInput.setText(result);
            }

            @Override
            public void onError(Exception e) {
                setWorking(false);
                settingsStatus.setText(e.getMessage());
            }
        });
    }

    private void signOut() {
        BackendClient.logout(this);
        FirebaseAuth.getInstance().signOut();
        Intent intent = new Intent(this, LoginActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
        finishAffinity();
    }

    private void setWorking(boolean working) {
        apiKeyAction.setEnabled(!working);
        saveSourcesButton.setEnabled(!working);
        signOutButton.setEnabled(!working);
        apiKeyInput.setEnabled(!working ? (editingApiKey || (settingsData != null && !settingsData.isGeminiKeySet())) : false);
    }
}
