import json
import os
import secrets
import time
from datetime import datetime
from typing import Dict, Optional


class AccessManager:
    def __init__(self, data_file='users_access.json'):
        self.data_file = data_file
        self.data = {'users': {}, 'invites': {}}
        self.load()

    def load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print('Ошибка загрузки: ' + str(e))

    def save(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def create_invite(self, created_by, duration_days=10, max_uses=1):
        code = secrets.token_hex(6).upper()
        code = '-'.join([code[i:i+4] for i in range(0, len(code), 4)])
        self.data['invites'][code] = {
            'created_by': created_by,
            'created_at': time.time(),
            'duration_days': duration_days,
            'max_uses': max_uses,
            'used_by': [],
            'active': True
        }
        self.save()
        return code

    def use_invite(self, code, user_id, username='', first_name=''):
        if code not in self.data['invites']:
            return False
        invite = self.data['invites'][code]
        if not invite.get('active', True):
            return False
        if len(invite['used_by']) >= invite['max_uses']:
            return False
        if user_id in invite['used_by']:
            return self.has_access(user_id)
        invite['used_by'].append(user_id)
        duration_days = invite.get('duration_days', 10)
        access_until = time.time() + duration_days * 86400
        self.data['users'][str(user_id)] = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'access_until': access_until,
            'granted_by': 'invite:' + code,
            'granted_at': time.time(),
            'note': 'Активирован инвайт на ' + str(duration_days) + ' дней'
        }
        self.save()
        return True

    def deactivate_invite(self, code):
        if code in self.data['invites']:
            self.data['invites'][code]['active'] = False
            self.save()
            return True
        return False

    def get_active_invites(self):
        return {k: v for k, v in self.data['invites'].items() if v.get('active', True)}

    def get_all_invites(self):
        return self.data['invites']

    def has_access(self, user_id):
        user_key = str(user_id)
        if user_key not in self.data['users']:
            return False
        user = self.data['users'][user_key]
        if not user.get('access_until'):
            return False
        return user['access_until'] > time.time()

    def grant_access(self, user_id, days, granted_by, username='', first_name='', note=''):
        user_key = str(user_id)
        now = time.time()
        if user_key in self.data['users']:
            user = self.data['users'][user_key]
            current_until = user.get('access_until', now)
            if current_until > now:
                new_until = current_until + days * 86400
            else:
                new_until = now + days * 86400
            user['access_until'] = new_until
            if username:
                user['username'] = username
            if first_name:
                user['first_name'] = first_name
            user['note'] = 'Продлен на ' + str(days) + ' дней. ' + note
        else:
            self.data['users'][user_key] = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'access_until': now + days * 86400,
                'granted_by': str(granted_by),
                'granted_at': now,
                'note': note or ('Выдан доступ на ' + str(days) + ' дней')
            }
        self.save()
        return True

    def revoke_access(self, user_id):
        user_key = str(user_id)
        if user_key in self.data['users']:
            self.data['users'][user_key]['access_until'] = 0
            self.data['users'][user_key]['note'] = 'Доступ отозван'
            self.save()
            return True
        return False

    def remove_user(self, user_id):
        user_key = str(user_id)
        if user_key in self.data['users']:
            del self.data['users'][user_key]
            self.save()
            return True
        return False

    def get_user_info(self, user_id):
        return self.data['users'].get(str(user_id))

    def get_all_users(self):
        return self.data['users']

    def get_active_users(self):
        now = time.time()
        return {k: v for k, v in self.data['users'].items() if v.get('access_until', 0) > now}

    def get_expired_users(self):
        now = time.time()
        return {k: v for k, v in self.data['users'].items() if v.get('access_until', 0) <= now}

    def get_access_remaining_days(self, user_id):
        user = self.get_user_info(user_id)
        if not user or not user.get('access_until'):
            return 0
        remaining = user['access_until'] - time.time()
        if remaining <= 0:
            return 0
        return int(remaining / 86400)

    def format_access_until(self, user_id):
        user = self.get_user_info(user_id)
        if not user or not user.get('access_until'):
            return 'нет доступа'
        if user['access_until'] <= time.time():
            return 'истек'
        return datetime.fromtimestamp(user['access_until']).strftime('%d.%m.%Y %H:%M')
