package com.sourcebruh.android;

import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.sourcebruh.android.model.SearchResult;
import com.sourcebruh.android.network.BackendClient;
import com.sourcebruh.android.ui.SearchResultsAdapter;

import java.util.ArrayList;
import java.util.List;

public class ResultsActivity extends AppCompatActivity {

    private static final int PAGE_SIZE = 18;

    private SearchResultsAdapter adapter;
    private ViewLoadingController loadingController;
    private String query;
    private final List<SearchResult> results = new ArrayList<>();
    private boolean isLoading = false;
    private boolean reachedEnd = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_results);

        query = getIntent().getStringExtra("query");
        if (TextUtils.isEmpty(query)) {
            Toast.makeText(this, "Missing query", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        Toolbar toolbar = findViewById(R.id.results_toolbar);
        TextView title = findViewById(R.id.results_title);
        title.setText(getString(R.string.searching));
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayShowTitleEnabled(false);
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
        }
        toolbar.setNavigationIcon(R.drawable.ic_back);
        toolbar.setNavigationOnClickListener(v -> finish());

        RecyclerView resultsList = findViewById(R.id.results_list);
        GridLayoutManager layoutManager = new GridLayoutManager(this, 3);
        resultsList.setLayoutManager(layoutManager);
        adapter = new SearchResultsAdapter(this, new ArrayList<>(), normaliseBaseUrl(getString(R.string.backend_base_url)));
        resultsList.setAdapter(adapter);

        loadingController = new ViewLoadingController(findViewById(R.id.results_progress), findViewById(R.id.empty_state), title);
        loadingController.showEmpty(false);

        resultsList.addOnScrollListener(new RecyclerView.OnScrollListener() {
            @Override
            public void onScrolled(@NonNull RecyclerView recyclerView, int dx, int dy) {
                super.onScrolled(recyclerView, dx, dy);
                if (dy <= 0) {
                    return;
                }
                int visibleItemCount = layoutManager.getChildCount();
                int totalItemCount = layoutManager.getItemCount();
                int firstVisibleItemPosition = layoutManager.findFirstVisibleItemPosition();

                if (!isLoading && !reachedEnd && (visibleItemCount + firstVisibleItemPosition) >= totalItemCount - 3) {
                    loadMore();
                }
            }
        });

        loadMore();
    }

    @Override
    protected void onStart() {
        super.onStart();
        FirebaseUser user = FirebaseAuth.getInstance().getCurrentUser();
        if (user == null) {
            finish();
        }
    }

    private void loadMore() {
        if (isLoading || reachedEnd) {
            return;
        }
        isLoading = true;
        loadingController.showLoading(true);
        final int target = results.size() + PAGE_SIZE;
        BackendClient.search(this, query, target, new BackendClient.BackendCallback<List<SearchResult>>() {
            @Override
            public void onSuccess(List<SearchResult> fetched) {
                isLoading = false;
                loadingController.showLoading(false);
                updateTitle();
                if (fetched == null || fetched.isEmpty()) {
                    if (results.isEmpty()) {
                        loadingController.showEmpty(true);
                    }
                    reachedEnd = true;
                    return;
                }
                List<SearchResult> newItems = new ArrayList<>();
                for (int i = results.size(); i < fetched.size(); i++) {
                    newItems.add(fetched.get(i));
                }
                if (results.isEmpty()) {
                    results.addAll(fetched);
                    adapter.updateItems(results);
                } else if (!newItems.isEmpty()) {
                    results.addAll(newItems);
                    adapter.appendItems(newItems);
                } else {
                    reachedEnd = true;
                }
                loadingController.showEmpty(results.isEmpty());
            }

            @Override
            public void onError(Exception e) {
                isLoading = false;
                loadingController.showLoading(false);
                Toast.makeText(ResultsActivity.this, e.getMessage(), Toast.LENGTH_LONG).show();
            }
        });
    }

    private void updateTitle() {
        TextView title = findViewById(R.id.results_title);
        if (results.isEmpty()) {
            title.setText(getString(R.string.searching));
        } else {
            title.setText(query);
        }
    }

    private String normaliseBaseUrl(String base) {
        if (TextUtils.isEmpty(base)) {
            return "";
        }
        return base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
    }

    private static class ViewLoadingController {
        private final View progress;
        private final View emptyView;
        private final TextView titleView;

        ViewLoadingController(View progress, View emptyView, TextView titleView) {
            this.progress = progress;
            this.emptyView = emptyView;
            this.titleView = titleView;
        }

        void showLoading(boolean show) {
            progress.setVisibility(show ? View.VISIBLE : View.GONE);
        }

        void showEmpty(boolean show) {
            emptyView.setVisibility(show ? View.VISIBLE : View.GONE);
            if (show) {
                titleView.setText(R.string.no_results);
            }
        }
    }
}
