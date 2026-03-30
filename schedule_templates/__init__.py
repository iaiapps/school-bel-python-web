import json
import os

TEMPLATES_DIR = os.path.dirname(os.path.abspath(__file__))

def get_template(name):
    filepath = os.path.join(TEMPLATES_DIR, f"{name}.json")
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def list_templates():
    templates = []
    for filename in os.listdir(TEMPLATES_DIR):
        if filename.endswith('.json') and not filename.startswith('__'):
            template_name = filename[:-5]
            data = get_template(template_name)
            if data:
                templates.append({
                    'name': template_name,
                    'display_name': data.get('name', template_name),
                    'description': data.get('description', '')
                })
    return templates

def expand_template(template_data, category, default_sound=None):
    if default_sound is None:
        default_sound = template_data.get('default_sound', 'bell/shift.wav')
    
    schedules = []
    hari_antara_schedule = []
    processed_days = set()
    
    for day_name in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat']:
        if day_name in processed_days:
            continue
            
        day_data = template_data['days'].get(day_name)
        
        if isinstance(day_data, str):
            ref_day = day_data
            if ref_day not in processed_days:
                continue
            if ref_day == 'Selasa' and hari_antara_schedule:
                for t, a, s in hari_antara_schedule:
                    day_schedule = (day_name, t, a, s, category)
                    schedules.append(day_schedule)
                processed_days.add(day_name)
        elif isinstance(day_data, list):
            day_schedule = []
            for item in day_data:
                sound = item.get('sound', default_sound)
                day_schedule.append((day_name, item['time'], item['activity'], sound, category))
            schedules.extend(day_schedule)
            processed_days.add(day_name)
            
            if day_name == 'Selasa':
                hari_antara_schedule = [(t, a, s) for _, t, a, s, _ in day_schedule]
    
    return schedules
