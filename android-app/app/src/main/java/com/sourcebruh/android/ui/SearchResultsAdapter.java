package com.sourcebruh.android.ui;

import android.content.Context;
import android.text.TextUtils;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.bumptech.glide.Glide;
import com.bumptech.glide.load.resource.bitmap.CenterCrop;
import com.sourcebruh.android.R;
import com.sourcebruh.android.model.SearchResult;

import java.util.ArrayList;
import java.util.List;

import jp.wasabeef.glide.transformations.BlurTransformation;

public class SearchResultsAdapter extends RecyclerView.Adapter<SearchResultsAdapter.ViewHolder> {

    private final List<SearchResult> items = new ArrayList<>();
    private final LayoutInflater inflater;
    private final String baseUrl;

    public SearchResultsAdapter(Context context, List<SearchResult> seed, String baseUrl) {
        this.inflater = LayoutInflater.from(context);
        if (seed != null) {
            this.items.addAll(seed);
        }
        this.baseUrl = baseUrl;
    }

    public void updateItems(List<SearchResult> updated) {
        this.items.clear();
        if (updated != null) {
            this.items.addAll(updated);
        }
        notifyDataSetChanged();
    }

    public void appendItems(List<SearchResult> more) {
        if (more == null || more.isEmpty()) {
            return;
        }
        int start = items.size();
        items.addAll(more);
        notifyItemRangeInserted(start, more.size());
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = inflater.inflate(R.layout.item_result_image, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        SearchResult item = items.get(position);
        String thumb = item.getThumbUrl();
        if (!TextUtils.isEmpty(thumb)) {
            if (thumb.startsWith("/")) {
                thumb = baseUrl + thumb;
            } else if (!thumb.startsWith("http")) {
                thumb = baseUrl + "/" + thumb;
            }
        }
        Glide.with(holder.imageView.getContext())
                .load(TextUtils.isEmpty(thumb) ? null : thumb)
                .thumbnail(Glide.with(holder.imageView.getContext())
                        .load(R.drawable.login_background)
                        .transform(new CenterCrop(), new BlurTransformation(25, 3)))
                .transform(new CenterCrop())
                .placeholder(R.drawable.image_placeholder)
                .error(R.drawable.image_placeholder)
                .into(holder.imageView);

        boolean hasDescription = !TextUtils.isEmpty(item.getDescription());
        boolean hasAlbum = !TextUtils.isEmpty(item.getAlbumTitle());
        if (hasDescription || hasAlbum) {
            holder.metadata.setVisibility(View.VISIBLE);
            holder.description.setText(hasDescription ? item.getDescription() : "");
            holder.description.setVisibility(hasDescription ? View.VISIBLE : View.GONE);
            holder.album.setText(hasAlbum ? item.getAlbumTitle() : "");
            holder.album.setVisibility(hasAlbum ? View.VISIBLE : View.GONE);
        } else {
            holder.metadata.setVisibility(View.GONE);
        }
    }

    @Override
    public int getItemCount() {
        return items.size();
    }

    public static class ViewHolder extends RecyclerView.ViewHolder {
        final ImageView imageView;
        final LinearLayout metadata;
        final TextView description;
        final TextView album;

        public ViewHolder(@NonNull View itemView) {
            super(itemView);
            imageView = itemView.findViewById(R.id.result_image);
            metadata = itemView.findViewById(R.id.result_metadata);
            description = itemView.findViewById(R.id.result_description);
            album = itemView.findViewById(R.id.result_album);
        }
    }
}
