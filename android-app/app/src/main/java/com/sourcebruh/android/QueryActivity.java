package com.sourcebruh.android;

import android.content.Intent;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

public class QueryActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_query);

        EditText queryInput = findViewById(R.id.query_input);
        ImageView settingsIcon = findViewById(R.id.settings_icon);

        queryInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                String query = queryInput.getText().toString();
                if (!query.isEmpty()) {
                    Intent intent = new Intent(QueryActivity.this, ResultsActivity.class);
                    intent.putExtra("query", query);
                    startActivity(intent);
                }
                return true;
            }
            return false;
        });

        settingsIcon.setOnClickListener(v -> startActivity(new Intent(QueryActivity.this, SettingsActivity.class)));
    }
}
