import os
import json
import glob
import csv
from collections import defaultdict

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    flagged_json_path = os.path.join(repo_root, 'data', 'flagged_config_leakage.json')
    
    with open(flagged_json_path, 'r', encoding='utf-8') as f:
        flagged_data = json.load(f)
    
    # 1. Determine exact set of conversations to remove
    convos_flags = defaultdict(list)
    for r in flagged_data:
        key = (r['file_path'], r['convo_index'])
        convos_flags[key].append(r)

    to_remove_rel = set() # (rel_path, old_index)
    preserved_reasons = []

    for (fpath, idx), flags in convos_flags.items():
        param_types = set(f['config_parameter'] for f in flags)
        rel_path = os.path.relpath(fpath, os.path.join(repo_root, 'data'))
        
        # Rule 1: Exclude convos where the ONLY issue is 'difficulty (general word)'
        if param_types == {'difficulty (general word)'}:
            preserved_reasons.append((rel_path, idx, 'only difficulty (general word)'))
            continue
            
        # Rule 2: Exclude convos where matched_text contains 'medium' and that is the only difficulty issue
        if param_types == {'difficulty', 'difficulty (general word)'}:
            has_medium = any('medium' in f.get('matched_text', '').lower() for f in flags)
            if has_medium:
                preserved_reasons.append((rel_path, idx, 'medium difficulty only'))
                continue
                
        to_remove_rel.add((rel_path, idx))

    print(f"Identified {len(to_remove_rel)} conversations to remove across the dataset.")
    print(f"Preserved {len(preserved_reasons)} conversations based on user exceptions:")
    for pr in preserved_reasons:
        print(f"  Preserved: {pr[0]} [index {pr[1]}] ({pr[2]})")

    # Group deletions by file
    deletions_by_file = defaultdict(set)
    for rel_path, idx in to_remove_rel:
        deletions_by_file[rel_path].add(idx)

    # 2. Process data/, output/, jev_output/, jev_output2/
    folders = ['data', 'output', 'jev_output', 'jev_output2']
    old_to_new_index = {} # (rel_path, old_idx) -> new_idx
    empty_files_count = 0

    # First, calculate index mapping for all affected and unaffected files in data/
    all_data_files = sorted(glob.glob(os.path.join(repo_root, 'data', '**', '*.json'), recursive=True))
    for df in all_data_files:
        if df.endswith('flagged_config_leakage.json'):
            continue
        rel_path = os.path.relpath(df, os.path.join(repo_root, 'data'))
        with open(df, 'r', encoding='utf-8') as fp:
            items = json.load(fp)
            
        del_indices = deletions_by_file.get(rel_path, set())
        new_idx = 0
        for old_idx in range(len(items)):
            if old_idx not in del_indices:
                old_to_new_index[(rel_path, old_idx)] = new_idx
                new_idx += 1

    # Perform modifications across folders
    modified_counts = defaultdict(int)
    for rel_path, del_indices in deletions_by_file.items():
        for folder in folders:
            target_path = os.path.join(repo_root, folder, rel_path)
            if not os.path.exists(target_path):
                print(f"Warning: File {target_path} does not exist.")
                continue
                
            with open(target_path, 'r', encoding='utf-8') as fp:
                items = json.load(fp)
                
            filtered_items = []
            for old_idx, item in enumerate(items):
                if old_idx not in del_indices:
                    # In output, jev_output, jev_output2, re-index conversation_index
                    if folder in ['output', 'jev_output', 'jev_output2']:
                        if isinstance(item, dict) and 'conversation_index' in item:
                            item['conversation_index'] = len(filtered_items)
                    filtered_items.append(item)
                    
            if len(filtered_items) == 0:
                empty_files_count += 1
                
            with open(target_path, 'w', encoding='utf-8') as fp:
                json.dump(filtered_items, fp, indent=2, ensure_ascii=False)
                
            modified_counts[folder] += 1

    print(f"Modified {modified_counts['data']} files in data/ (removed {len(to_remove_rel)} items).")
    print(f"Modified {modified_counts['output']} files in output/ (re-indexed conversation_index).")
    print(f"Modified {modified_counts['jev_output']} files in jev_output/ (re-indexed conversation_index).")
    print(f"Modified {modified_counts['jev_output2']} files in jev_output2/ (re-indexed conversation_index).")
    print(f"Empty files retained as []: {empty_files_count // 4} unique files.")

    # 3. Process annotation_set/
    ann_subsets = ['random_sample', 'metric_profile_sample', 'judge_disagreement_sample']
    removed_annotations = []

    for subset in ann_subsets:
        annotations_file = os.path.join(repo_root, 'annotation_set', subset, 'annotations.json')
        manifest_file = os.path.join(repo_root, 'annotation_set', subset, 'manifest.json')
        summary_file = os.path.join(repo_root, 'annotation_set', subset, 'selection_summary.json')
        
        # A. Process annotations.json
        with open(annotations_file, 'r', encoding='utf-8') as fp:
            annotations = json.load(fp)
            
        kept_annotations = []
        for ann in annotations:
            src = ann['source']
            rel_path = src['relative_path']
            old_idx = src['index']
            
            if (rel_path, old_idx) in to_remove_rel:
                # Flagged for removal
                flags = convos_flags[(f"data/{rel_path}", old_idx)]
                reasons = list(set(f['config_parameter'] for f in flags))
                removed_annotations.append({
                    'annotation_id': ann['annotation_id'],
                    'sampling_strategy': subset,
                    'relative_path': rel_path,
                    'original_index': old_idx,
                    'flagged_parameters': ", ".join(reasons)
                })
            else:
                # Keep annotation: Keep annotation_id UNCHANGED, update source.index to match data/ re-indexing
                src['index'] = old_to_new_index[(rel_path, old_idx)]
                kept_annotations.append(ann)
                
        with open(annotations_file, 'w', encoding='utf-8') as fp:
            json.dump(kept_annotations, fp, indent=2, ensure_ascii=False)
            
        # B. Process manifest.json
        if os.path.exists(manifest_file):
            with open(manifest_file, 'r', encoding='utf-8') as fp:
                manifest = json.load(fp)
                
            kept_selected = []
            for sel in manifest.get('selected_conversations', []):
                rel_path = sel['relative_path']
                old_idx = sel['index']
                if (rel_path, old_idx) not in to_remove_rel:
                    sel['index'] = old_to_new_index[(rel_path, old_idx)]
                    kept_selected.append(sel)
                    
            manifest['selected_conversations'] = kept_selected
            manifest['actual_sample_size'] = len(kept_selected)
            
            with open(manifest_file, 'w', encoding='utf-8') as fp:
                json.dump(manifest, fp, indent=2, ensure_ascii=False)
                
        # C. Process selection_summary.json
        if os.path.exists(summary_file):
            with open(summary_file, 'r', encoding='utf-8') as fp:
                summary = json.load(fp)
            if 'actual_sample_size' in summary:
                summary['actual_sample_size'] = len(kept_annotations)
            if 'number_selected' in summary:
                summary['number_selected'] = len(kept_annotations)
            with open(summary_file, 'w', encoding='utf-8') as fp:
                json.dump(summary, fp, indent=2, ensure_ascii=False)

    print(f"\nRemoved {len(removed_annotations)} annotations across annotation_set:")
    for ra in removed_annotations:
        print(f"  {ra['annotation_id']} ({ra['sampling_strategy']}): {ra['relative_path']} [orig index {ra['original_index']}] - Reasons: {ra['flagged_parameters']}")

    # 4. Output removed annotations report
    removed_json_path = os.path.join(repo_root, 'annotation_set', 'removed_annotations.json')
    with open(removed_json_path, 'w', encoding='utf-8') as fp:
        json.dump(removed_annotations, fp, indent=2)
    print(f"Saved removed annotations JSON to {removed_json_path}")

    removed_csv_path = os.path.join(repo_root, 'annotation_set', 'removed_annotations.csv')
    fieldnames = ['annotation_id', 'sampling_strategy', 'relative_path', 'original_index', 'flagged_parameters']
    with open(removed_csv_path, 'w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for ra in removed_annotations:
            writer.writerow(ra)
    print(f"Saved removed annotations CSV to {removed_csv_path}")

if __name__ == '__main__':
    main()
