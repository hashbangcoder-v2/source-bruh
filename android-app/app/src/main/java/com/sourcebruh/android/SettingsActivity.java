package com.sourcebruh.android;

import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.google.firebase.firestore.DocumentReference;
import com.google.firebase.firestore.FirebaseFirestore;

import java.util.HashMap;
import java.util.Map;

public class SettingsActivity extends AppCompatActivity {

    private EditText apiKeyEditText;
    private EditText sourcesEditText;
    private TextView userNameTextView;
    private TextView userEmailTextView;

    private FirebaseFirestore db;
    private FirebaseUser currentUser;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        apiKeyEditText = findViewById(R.id.api_key);
        sourcesEditText = findViewById(R.id.sources);
        userNameTextView = findViewById(R.id.user_name);
        userEmailTextView = findViewById(R.id.user_email);
        Button saveButton = findViewById(R.id.save_button);

        db = FirebaseFirestore.getInstance();
        currentUser = FirebaseAuth.getInstance().getCurrentUser();

        if (currentUser != null) {
            userNameTextView.setText("Name: " + currentUser.getDisplayName());
            userEmailTextView.setText("Email: " + currentUser.getEmail());
            loadSettings();
        }

        saveButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                saveSettings();
            }
        });
    }

    private void loadSettings() {
        DocumentReference userDocRef = db.collection("users").document(currentUser.getUid());
        userDocRef.get().addOnSuccessListener(documentSnapshot -> {
            if (documentSnapshot.exists()) {
                apiKeyEditText.setText(documentSnapshot.getString("apiKey"));
                sourcesEditText.setText(documentSnapshot.getString("sources"));
            }
        });
    }

    private void saveSettings() {
        String apiKey = apiKeyEditText.getText().toString();
        String sources = sourcesEditText.getText().toString();

        if (apiKey.isEmpty()) {
            Toast.makeText(this, "API Key is mandatory", Toast.LENGTH_SHORT).show();
            return;
        }

        Map<String, Object> settings = new HashMap<>();
        settings.put("apiKey", apiKey);
        settings.put("sources", sources);

        db.collection("users").document(currentUser.getUid()).set(settings)
                .addOnSuccessListener(aVoid -> Toast.makeText(SettingsActivity.this, "Settings saved", Toast.LENGTH_SHORT).show())
                .addOnFailureListener(e -> Toast.makeText(SettingsActivity.this, "Error saving settings", Toast.LENGTH_SHORT).show());
    }
}
