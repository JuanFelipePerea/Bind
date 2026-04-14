"""
Forms — ModelForms reales para los módulos de BIND.

Reemplaza el patrón SimpleNamespace que se usaba en views.py
para construir objetos falsos que imitaban formularios.
"""

from django import forms
from .models import Task, Attendee, Checklist, File


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'status', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50',
                'placeholder': 'Título de la tarea',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50 resize-none',
                'placeholder': 'Descripción (opcional)',
                'rows': 3,
            }),
            'priority': forms.Select(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50',
            }),
            'status': forms.Select(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50',
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50',
            }),
        }
        labels = {
            'title': 'Título',
            'description': 'Descripción',
            'priority': 'Prioridad',
            'status': 'Estado',
            'due_date': 'Fecha límite',
        }


class AttendeeForm(forms.ModelForm):
    class Meta:
        model = Attendee
        fields = ['name', 'email', 'status']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50',
                'placeholder': 'Nombre completo',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50',
                'placeholder': 'correo@ejemplo.com',
            }),
            'status': forms.Select(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50',
            }),
        }
        labels = {
            'name': 'Nombre',
            'email': 'Email',
            'status': 'Estado',
        }


class ChecklistForm(forms.ModelForm):
    class Meta:
        model = Checklist
        fields = ['title']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50',
                'placeholder': 'Nombre del checklist',
            }),
        }
        labels = {
            'title': 'Título',
        }


class FileForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['name', 'file_path', 'file_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50',
                'placeholder': 'Nombre del archivo',
            }),
            'file_path': forms.TextInput(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50',
                'placeholder': '/ruta/al/archivo.pdf',
            }),
            'file_type': forms.Select(attrs={
                'class': 'w-full bg-white/50 dark:bg-black/20 rounded-xl px-4 py-3 text-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-teal-500/50',
            }),
        }
        labels = {
            'name': 'Nombre',
            'file_path': 'Ruta del archivo',
            'file_type': 'Tipo',
        }
