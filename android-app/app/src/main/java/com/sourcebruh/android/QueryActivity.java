package com.sourcebruh.android;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.sourcebruh.android.model.SettingsData;
import com.sourcebruh.android.network.BackendClient;

public class QueryActivity extends AppCompatActivity {

    private EditText queryInput;
    private ImageButton queryButton;
    private ProgressBar searchProgress;
    private SettingsData settingsData;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_query);

        queryInput = findViewById(R.id.query_input);
        queryButton = findViewById(R.id.query_button);
        searchProgress = findViewById(R.id.search_progress);
        ImageView settingsIcon = findViewById(R.id.settings_icon);

        settingsIcon.setOnClickListener(v -> startActivity(new Intent(QueryActivity.this, SettingsActivity.class)));

        queryButton.setOnClickListener(v -> handleSearch());
        queryInput.setOnEditorActionListener((TextView v, int actionId, KeyEvent event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                handleSearch();
                return true;
            }
            return false;
        });
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
            Intent intent = new Intent(this, LoginActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            finish();
        }
    }

    private void handleSearch() {
        String query = queryInput.getText().toString().trim();
        if (TextUtils.isEmpty(query)) {
            return;
        }
        if (settingsData == null) {
            Toast.makeText(this, "Checking your setup…", Toast.LENGTH_SHORT).show();
            loadSettings();
            return;
        }
        if (!settingsData.isGeminiKeySet()) {
            new MaterialAlertDialogBuilder(this)
                    .setTitle(R.string.settings_api_key)
                    .setMessage(R.string.error_api_key_required)
                    .setPositiveButton(R.string.open_settings, (dialog, which) ->
                            startActivity(new Intent(QueryActivity.this, SettingsActivity.class)))
                    .setNegativeButton(R.string.dismiss, null)
                    .show();
            return;
        }
        setLoading(true);
        Intent intent = new Intent(QueryActivity.this, ResultsActivity.class);
        intent.putExtra("query", query);
        startActivity(intent);
    }

    private void loadSettings() {
        setLoading(true);
        BackendClient.fetchSettings(this, new BackendClient.BackendCallback<SettingsData>() {
            @Override
            public void onSuccess(SettingsData result) {
                settingsData = result;
                setLoading(false);
            }

            @Override
            public void onError(Exception e) {
                setLoading(false);
                Toast.makeText(QueryActivity.this, e.getMessage(), Toast.LENGTH_LONG).show();
            }
        });
    }

    private void setLoading(boolean loading) {
        if (queryButton == null) {
            return;
        }
        queryButton.setEnabled(!loading);
        searchProgress.setVisibility(loading ? View.VISIBLE : View.GONE);
    }
}
