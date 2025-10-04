package com.sourcebruh.android;

import android.os.Bundle;
import android.widget.GridView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.firebase.functions.FirebaseFunctions;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ResultsActivity extends AppCompatActivity {

    private GridView resultsGrid;
    private ImageAdapter imageAdapter;
    private List<String> imageUrls = new ArrayList<>();
    private FirebaseFunctions mFunctions;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_results);

        resultsGrid = findViewById(R.id.results_grid);
        imageAdapter = new ImageAdapter(this, imageUrls);
        resultsGrid.setAdapter(imageAdapter);

        mFunctions = FirebaseFunctions.getInstance();

        String query = getIntent().getStringExtra("query");
        if (query != null) {
            searchImages(query);
        }
    }

    private void searchImages(String query) {
        Map<String, Object> data = new HashMap<>();
        data.put("query", query);

        mFunctions.getHttpsCallable("searchImages")
                .call(data)
                .addOnCompleteListener(task -> {
                    if (task.isSuccessful()) {
                        List<String> newImageUrls = (List<String>) task.getResult().getData();
                        imageUrls.addAll(newImageUrls);
                        imageAdapter.notifyDataSetChanged();
                    } else {
                        Toast.makeText(ResultsActivity.this, "Error searching images", Toast.LENGTH_SHORT).show();
                    }
                });
    }
}
