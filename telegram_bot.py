#!/usr/bin/env python3
"""
Bot de Telegram para OpenShift Monitor
Proporciona comandos interactivos y notificaciones automáticas
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode
import json
import re

logger = logging.getLogger(__name__)

class OpenShiftTelegramBot:
    """Bot de Telegram para monitoreo de OpenShift"""
    
    def __init__(self, token: str, authorized_users: List[int], monitor: OpenShiftMonitor):
        """Inicializar el bot de Telegram"""
        self.token = token
        self.authorized_users = authorized_users
        self.monitor = monitor
        self.application = None
        self.callback_mapping = {}  # Mapeo de callback_data limpios a valores originales
        self.callback_counter = 0   # Contador para generar IDs únicos
        
    def _generate_callback_id(self, action: str, cluster_name: str, namespace_name: str = None) -> str:
        """Generar un ID único para callback_data"""
        self.callback_counter += 1
        callback_id = f"cb_{self.callback_counter:04d}"
        
        # Guardar el mapeo
        if namespace_name:
            self.callback_mapping[callback_id] = (action, cluster_name, namespace_name)
            logger.debug(f"Callback generado: {callback_id} -> ({action}, {cluster_name}, {namespace_name})")
        else:
            self.callback_mapping[callback_id] = (action, cluster_name)
            logger.debug(f"Callback generado: {callback_id} -> ({action}, {cluster_name})")
        
        # Limpiar mapeo si es muy grande (más de 1000 entradas)
        if len(self.callback_mapping) > 1000:
            logger.info("Limpiando mapeo de callbacks (muy grande)")
            self.callback_mapping.clear()
            self.callback_counter = 0
        
        return callback_id
    
    def _get_callback_data(self, callback_id: str):
        """Obtener los datos originales del callback_data"""
        data = self.callback_mapping.get(callback_id)
        if data:
            logger.debug(f"Callback resuelto: {callback_id} -> {data}")
        else:
            logger.warning(f"Callback no encontrado: {callback_id}")
        return data
    
    def _clean_callback_data(self, data: str) -> str:
        """Limpiar y validar callback_data para evitar errores de Telegram"""
        # Remover caracteres problemáticos y limitar longitud
        cleaned = re.sub(r'[^a-zA-Z0-9_-]', '_', data)
        # Limitar a 64 bytes (límite de Telegram)
        if len(cleaned.encode('utf-8')) > 64:
            # Si es muy largo, truncar y agregar hash
            hash_suffix = str(hash(data))[-8:]
            cleaned = cleaned[:50] + '_' + hash_suffix
        return cleaned

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Usuario"
        
        # Agregar chat_id a la lista de chats activos
        chat_id = update.effective_chat.id
        self.chat_ids.add(chat_id)
        
        welcome_message = f"""
🤖 **OpenShift Monitor Bot**

¡Hola {username}! Soy tu asistente para monitorear clusters OpenShift.

**🚀 Comandos principales:**
🎯 `/menu` - **Menú interactivo con botones** (RECOMENDADO)
📊 `/status` - Estado general de todos los clusters
📋 `/report [cluster]` - Generar reporte completo en /reports

**📁 Monitoreo detallado:**
📈 `/metricas [cluster]` - Métricas de recursos
⚙️ `/operadores [cluster]` - Estado de operadores
🖥️ `/nodos [cluster]` - Estado de nodos
📁 `/namespaces [cluster]` - Estado de namespaces
🐳 `/pods [cluster] [namespace]` - Estado de pods

**💡 Tips:**
• Usa `/menu` para acceso rápido y fácil
• Los reportes se guardan automáticamente en `/reports`
• Las alertas se envían automáticamente cuando hay problemas

**Ejemplos:**
• `/menu` - Menú interactivo
• `/report cluster-4vscj-1` - Generar reporte completo
• `/pods cluster-4vscj-1 openshift-monitoring` - Ver pods del namespace
        """
        
        await update.message.reply_text(
            welcome_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /menu - Mostrar menú interactivo"""
        await self.show_menu(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /ayuda - Redirigir a /menu"""
        await self.menu_command(update, context)
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostrar menú interactivo con botones"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Estado General", callback_data="status"),
                InlineKeyboardButton("📋 Generar Reporte", callback_data="report")
            ],
            [
                InlineKeyboardButton("⚙️ Operadores", callback_data="operators"),
                InlineKeyboardButton("🖥️ Nodos", callback_data="nodes")
            ],
            [
                InlineKeyboardButton("📁 Namespaces", callback_data="namespaces"),
                InlineKeyboardButton("🐳 Pods", callback_data="pods")
            ],
            [
                InlineKeyboardButton("❓ Ayuda", callback_data="help"),
                InlineKeyboardButton("🔄 Actualizar", callback_data="refresh")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = """
🎯 **MENÚ PRINCIPAL - Monitor OpenShift**

Selecciona una opción del menú:

📊 **Estado General** - Vista rápida del cluster
📋 **Generar Reporte** - Reporte completo en /reports
⚙️ **Operadores** - Estado de operadores del cluster
🖥️ **Nodos** - Estado de nodos del cluster
📁 **Namespaces** - Lista de namespaces
🐳 **Pods** - Estado de pods por namespace
❓ **Ayuda** - Información de comandos
🔄 **Actualizar** - Refrescar datos
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text=menu_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status - Estado general de todos los clusters"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        # Crear tabla formateada del estado general
        status_message = "📊 **Estado General de Clusters**\n\n"
        status_message += "| Cluster | Estado | Operadores | Nodos | Última Verificación |\n"
        status_message += "|---------|---------|------------|-------|---------------------|\n"
        
        for cluster_name, status in self.monitor.cluster_statuses.items():
            # Calcular tiempo transcurrido
            time_diff = datetime.now() - status.timestamp
            minutes_ago = int(time_diff.total_seconds() / 60)
            
            # Contar operadores y nodos
            total_operators = len(status.operators_status)
            ok_operators = sum(1 for s in status.operators_status.values() if s in ['AsExpected', 'OK', 'RollOutDone'])
            total_nodes = len(status.nodes_status)
            ok_nodes = sum(1 for is_up in status.nodes_status.values() if is_up)
            
            # Emoji de salud
            health_emoji = {
                "HEALTHY": "🟢",
                "WARNING": "🟡", 
                "CRITICAL": "🔴",
                "ERROR": "❌"
            }
            health_icon = health_emoji.get(status.overall_health, "❓")
            
            # Formatear nombre del cluster para la tabla
            display_name = cluster_name[:20] + "..." if len(cluster_name) > 20 else cluster_name
            
            status_message += f"| {display_name} | {health_icon} {status.overall_health} | {ok_operators}/{total_operators} | {ok_nodes}/{total_nodes} | {minutes_ago} min |\n"
        
        # Agregar resumen general
        total_clusters = len(self.monitor.cluster_statuses)
        healthy_clusters = sum(1 for s in self.monitor.cluster_statuses.values() if s.overall_health == "HEALTHY")
        warning_clusters = sum(1 for s in self.monitor.cluster_statuses.values() if s.overall_health == "WARNING")
        critical_clusters = sum(1 for s in self.monitor.cluster_statuses.values() if s.overall_health in ["CRITICAL", "ERROR"])
        
        status_message += f"\n**📈 Resumen General:**\n"
        status_message += f"🟢 Clusters saludables: {healthy_clusters}/{total_clusters}\n"
        if warning_clusters > 0:
            status_message += f"🟡 Clusters con advertencias: {warning_clusters}\n"
        if critical_clusters > 0:
            status_message += f"🔴 Clusters críticos: {critical_clusters}\n"
        
        await self.send_response(update, status_message, ParseMode.MARKDOWN)
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /report - Generar reporte completo y guardarlo en /reports"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        cluster_name = context.args[0] if context.args else list(self.monitor.cluster_statuses.keys())[0]
        
        if cluster_name not in self.monitor.cluster_statuses:
            available_clusters = ", ".join(self.monitor.cluster_statuses.keys())
            await self.send_response(update, f"❌ Cluster no encontrado. Disponibles: {available_clusters}")
            return
        
        # Mostrar mensaje de generación
        await self.send_response(update, f"📋 **Generando reporte completo para {cluster_name}...**\n\n⏳ Esto puede tomar unos segundos...")
        
        try:
            # Generar reporte usando el monitor
            report_content = self.monitor.generate_markdown_report(cluster_name)
            
            if report_content:
                # Crear directorio reports si no existe
                os.makedirs('reports', exist_ok=True)
                
                # Generar nombre de archivo con timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"reports/{cluster_name}_{timestamp}.md"
                
                # Guardar reporte en archivo
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                # Mensaje de confirmación
                success_message = f"""
✅ **Reporte Generado Exitosamente**

📁 **Archivo:** `{filename}`
🏠 **Cluster:** {cluster_name}
🕐 **Hora:** {datetime.now().strftime('%H:%M:%S')}

📊 **Contenido del Reporte:**
• Estado general del cluster
• Estado de operadores
• Estado de nodos
• Métricas de recursos
• Estado de namespaces y pods
• Problemas críticos detectados

💡 **Para ver el reporte completo:** Revisa el archivo en el directorio `/reports`
                """
                
                # Botones para más acciones
                keyboard = [
                    [
                        InlineKeyboardButton("📊 Estado Actual", callback_data="status"),
                        InlineKeyboardButton("🔄 Generar Otro", callback_data="report")
                    ],
                    [
                        InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")
                    ]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if update.callback_query:
                    await update.callback_query.edit_message_text(
                        text=success_message,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        text=success_message,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                logger.info(f"Reporte generado y guardado: {filename}")
                
            else:
                await self.send_response(update, f"❌ Error generando reporte para {cluster_name}")
                
        except Exception as e:
            error_message = f"❌ **Error generando reporte:**\n\n{str(e)}"
            await self.send_response(update, error_message)
            logger.error(f"Error generando reporte: {e}")
    
    async def informe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /informe - Generar reporte completo de un cluster (mantener compatibilidad)"""
        await self.report_command(update, context)
    
    async def metricas_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /metricas - Métricas de recursos de un cluster"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay métricas disponibles.")
            return
        
        cluster_name = context.args[0] if context.args else list(self.monitor.cluster_statuses.keys())[0]
        
        if cluster_name not in self.monitor.cluster_statuses:
            available_clusters = ", ".join(self.monitor.cluster_statuses.keys())
            await self.send_response(update, f"❌ Cluster no encontrado. Disponibles: {available_clusters}")
            return
        
        status = self.monitor.cluster_statuses[cluster_name]
        
        if not status.resource_metrics:
            await self.send_response(update, "⚠️ No hay métricas disponibles para este cluster.")
            return
        
        # Crear tabla formateada de métricas
        metrics_message = f"📈 **Métricas de Recursos: {cluster_name}**\n\n"
        
        # Crear tabla de métricas por nodo
        metrics_message += "| Nodo | CPU | Memoria |\n"
        metrics_message += "|------|-----|---------|\n"
        
        for node_name, node_metrics in status.resource_metrics.items():
            cpu_pct = node_metrics.get('cpu', 0)
            memory_pct = node_metrics.get('memory', 0)
            
            # Emojis para CPU
            cpu_emoji = "🟢" if cpu_pct < 50 else "🟡" if cpu_pct < 80 else "🔴"
            
            # Emojis para memoria
            memory_emoji = "🟢" if memory_pct < 50 else "🟡" if memory_pct < 80 else "🔴"
            
            metrics_message += f"| {node_name} | {cpu_emoji} {cpu_pct:.1f}% | {memory_emoji} {memory_pct:.1f}% |\n"
        
        # Agregar resumen y recomendaciones
        total_nodes = len(status.resource_metrics)
        high_cpu_nodes = sum(1 for metrics in status.resource_metrics.values() if metrics.get('cpu', 0) > 80)
        high_memory_nodes = sum(1 for metrics in status.resource_metrics.values() if metrics.get('memory', 0) > 80)
        
        metrics_message += f"\n**📊 Resumen:**\n"
        metrics_message += f"🖥️ Nodos monitoreados: {total_nodes}\n"
        if high_cpu_nodes > 0:
            metrics_message += f"🔥 CPU alta (>80%): {high_cpu_nodes} nodos\n"
        if high_memory_nodes > 0:
            metrics_message += f"💾 Memoria alta (>80%): {high_memory_nodes} nodos\n"
        
        # Recomendaciones
        if high_cpu_nodes > 0 or high_memory_nodes > 0:
            metrics_message += f"\n**⚠️ Recomendaciones:**\n"
            if high_cpu_nodes > 0:
                metrics_message += f"• Revisar carga de trabajo en nodos con CPU alta\n"
            if high_memory_nodes > 0:
                metrics_message += f"• Verificar fugas de memoria o pods con alto consumo\n"
        
        await self.send_response(update, metrics_message, ParseMode.MARKDOWN)
    
    async def operadores_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /operadores - Estado de operadores de un cluster"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        cluster_name = context.args[0] if context.args else list(self.monitor.cluster_statuses.keys())[0]
        
        if cluster_name not in self.monitor.cluster_statuses:
            available_clusters = ", ".join(self.monitor.cluster_statuses.keys())
            await self.send_response(update, f"❌ Cluster no encontrado. Disponibles: {available_clusters}")
            return
        
        status = self.monitor.cluster_statuses[cluster_name]
        
        # Crear tabla formateada similar a los reportes
        operators_message = f"⚙️ **Estado de Operadores: {cluster_name}**\n\n"
        
        # Crear tabla de operadores
        operators_message += "| Operador | Estado |\n"
        operators_message += "|----------|---------|\n"
        
        # Agrupar operadores por estado para mejor visualización
        healthy_operators = []
        warning_operators = []
        critical_operators = []
        
        for operator, operator_status in status.operators_status.items():
            if operator_status in ['AsExpected', 'OK', 'RollOutDone']:
                healthy_operators.append(operator)
            elif operator_status in ['Degraded', 'NotAvailable']:
                critical_operators.append(operator)
            else:
                warning_operators.append(operator)
        
        # Mostrar operadores críticos primero (si los hay)
        if critical_operators:
            for operator in critical_operators:
                operators_message += f"| {operator} | ⚠️ {status.operators_status[operator]} |\n"
        
        # Mostrar operadores con advertencias
        if warning_operators:
            for operator in warning_operators:
                operators_message += f"| {operator} | 🟡 {status.operators_status[operator]} |\n"
        
        # Mostrar operadores saludables
        for operator in healthy_operators:
            operators_message += f"| {operator} | ✅ OK |\n"
        
        # Agregar resumen
        total_operators = len(status.operators_status)
        healthy_count = len(healthy_operators)
        warning_count = len(warning_operators)
        critical_count = len(critical_operators)
        
        operators_message += f"\n**📊 Resumen:**\n"
        operators_message += f"🟢 Saludables: {healthy_count}\n"
        if warning_count > 0:
            operators_message += f"🟡 Advertencias: {warning_count}\n"
        if critical_count > 0:
            operators_message += f"🔴 Críticos: {critical_count}\n"
        operators_message += f"📈 Total: {total_operators} operadores"
        
        await self.send_response(update, operators_message, ParseMode.MARKDOWN)
    
    async def nodes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /nodos - Estado de nodos de un cluster"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        cluster_name = context.args[0] if context.args else list(self.monitor.cluster_statuses.keys())[0]
        
        if cluster_name not in self.monitor.cluster_statuses:
            available_clusters = ", ".join(self.monitor.cluster_statuses.keys())
            await self.send_response(update, f"❌ Cluster no encontrado. Disponibles: {available_clusters}")
            return
        
        status = self.monitor.cluster_statuses[cluster_name]
        
        # Crear mensaje de estado de nodos
        nodes_message = f"🖥️ **Estado de Nodos: {cluster_name}**\n\n"
        
        # Crear tabla de nodos
        nodes_message += "| Nodo | Estado | CPU | Memoria |\n"
        nodes_message += "|------|---------|-----|---------|\n"
        
        total_nodes = len(status.nodes_status)
        ok_nodes = 0
        
        for node_name, is_up in status.nodes_status.items():
            status_emoji = "✅" if is_up else "❌"
            status_text = "Operativo" if is_up else "Caído"
            
            if is_up:
                ok_nodes += 1
            
            # Obtener métricas del nodo si están disponibles
            cpu_pct = "N/A"
            memory_pct = "N/A"
            
            if hasattr(status, 'resource_metrics') and status.resource_metrics:
                if node_name in status.resource_metrics:
                    node_metrics = status.resource_metrics[node_name]
                    cpu_pct = f"{node_metrics.get('cpu', 0):.1f}%" if 'cpu' in node_metrics else "N/A"
                    memory_pct = f"{node_metrics.get('memory', 0):.1f}%" if 'memory' in node_metrics else "N/A"
            
            nodes_message += f"| {node_name} | {status_emoji} {status_text} | {cpu_pct} | {memory_pct} |\n"
        
        # Agregar resumen
        nodes_message += f"\n**📊 Resumen:**\n"
        nodes_message += f"🖥️ Total de nodos: {total_nodes}\n"
        nodes_message += f"✅ Operativos: {ok_nodes}\n"
        nodes_message += f"❌ Caídos: {total_nodes - ok_nodes}\n"
        
        # Agregar recomendaciones si hay nodos caídos
        if ok_nodes < total_nodes:
            nodes_message += f"\n**⚠️ Recomendaciones:**\n"
            nodes_message += f"• Verificar estado físico de nodos caídos\n"
            nodes_message += f"• Revisar logs del sistema operativo\n"
            nodes_message += f"• Verificar conectividad de red\n"
        
        await self.send_response(update, nodes_message, ParseMode.MARKDOWN)
    
    async def show_namespace_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, cluster_name: str):
        """Mostrar selección de namespace para ver pods"""
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        if cluster_name not in self.monitor.cluster_statuses:
            await self.send_response(update, f"❌ Cluster '{cluster_name}' no encontrado.")
            return
        
        status = self.monitor.cluster_statuses[cluster_name]
        
        if not hasattr(status, 'namespaces_status') or not status.namespaces_status:
            await self.send_response(update, f"⚠️ No hay información de namespaces disponible para {cluster_name}")
            return
        
        # Crear botones para cada namespace con callback_data único
        keyboard = []
        for namespace_name in status.namespaces_status.keys():
            # Generar callback_data único
            callback_id = self._generate_callback_id("pods", cluster_name, namespace_name)
            keyboard.append([InlineKeyboardButton(f"📁 {namespace_name}", callback_data=callback_id)])
        
        # Botón para volver a la selección de cluster
        keyboard.append([InlineKeyboardButton("🔙 Volver a Clusters", callback_data="pods")])
        keyboard.append([InlineKeyboardButton("🏠 Menú Principal", callback_data="menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"""
📁 **Selecciona un Namespace**

Para ver **Pods** en {cluster_name}, selecciona un namespace:

{chr(10).join([f"• {ns}" for ns in status.namespaces_status.keys()])}

🔙 **Para volver:** Usa los botones de navegación
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    

    
    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /ping - Verificar conectividad del bot"""
        if not self.is_authorized(update):
            return
            
        await update.message.reply_text(
            "🏓 **Pong!** El bot está funcionando correctamente.\n"
            f"🕐 Hora del servidor: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    async def tiempo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /tiempo - Última verificación de cada cluster"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await update.message.reply_text("⚠️ No hay datos disponibles.")
            return
        
        tiempo_message = "🕐 **Última Verificación de Clusters**\n\n"
        
        for cluster_name, status in self.monitor.cluster_statuses.items():
            time_diff = datetime.now() - status.timestamp
            minutes_ago = int(time_diff.total_seconds() / 60)
            
            if minutes_ago < 5:
                emoji = "🟢"
                status_text = "Reciente"
            elif minutes_ago < 15:
                emoji = "🟡"
                status_text = "Normal"
            else:
                emoji = "🔴"
                status_text = "Antiguo"
            
            tiempo_message += f"{emoji} **{cluster_name}:** {minutes_ago} min atrás ({status_text})\n"
        
        await update.message.reply_text(
            tiempo_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar callbacks de botones inline"""
        query = update.callback_query
        await query.answer()  # Responder al callback query
        
        if not self.is_authorized(update):
            return
        
        data = query.data
        
        # Manejar acciones del menú principal
        if data == "status":
            await self.status_command(update, context)
        elif data == "report":
            await self.report_command(update, context)
        elif data == "operators":
            # Mostrar lista de clusters para seleccionar
            await self.show_cluster_selection(update, context, "operators")
        elif data == "nodes":
            # Mostrar lista de clusters para seleccionar
            await self.show_cluster_selection(update, context, "nodes")
        elif data == "namespaces":
            # Mostrar lista de clusters para seleccionar
            await self.show_cluster_selection(update, context, "namespaces")
        elif data == "pods":
            # Mostrar lista de clusters para seleccionar
            await self.show_cluster_selection(update, context, "pods")
        elif data == "help":
            await self.show_help_menu(update, context)
        elif data == "refresh":
            await self.handle_refresh_action(update, context)
        elif data == "menu":
            await self.show_menu(update, context)
        # Manejar acciones específicas de cluster usando el sistema de mapeo
        elif data.startswith("cb_"):
            # Es un callback_data único, obtener los datos originales
            callback_data = self._get_callback_data(data)
            if callback_data:
                if len(callback_data) == 2:
                    # Formato: (action, cluster_name)
                    action, cluster_name = callback_data
                    
                    if action == "metricas":
                        context.args = [cluster_name]
                        await self.metricas_command(update, context)
                    elif action == "operadores":
                        context.args = [cluster_name]
                        await self.operadores_command(update, context)
                    elif action == "operators":
                        context.args = [cluster_name]
                        await self.operadores_command(update, context)
                    elif action == "nodes":
                        context.args = [cluster_name]
                        await self.nodes_command(update, context)
                    elif action == "namespaces":
                        context.args = [cluster_name]
                        await self.namespaces_command(update, context)
                    elif action == "pods":
                        # Para pods necesitamos mostrar namespaces primero
                        await self.show_namespace_selection(update, context, cluster_name)
                    elif action == "actualizar":
                        await query.edit_message_text("🔄 Actualizando datos...")
                        # Aquí podrías forzar una actualización del monitor
                        # Por ahora solo mostramos el mensaje
                        await query.edit_message_text("✅ Datos actualizados. Usa /status para ver el estado actual.")
                
                elif len(callback_data) == 3:
                    # Formato: (action, cluster_name, namespace_name)
                    action, cluster_name, namespace_name = callback_data
                    
                    if action == "pods":
                        context.args = [cluster_name, namespace_name]
                        await self.pods_command(update, context)
        # Mantener compatibilidad con el formato anterior por si acaso
        elif "_" in data:
            parts = data.split('_', 2)  # Permitir hasta 2 separadores
            
            if len(parts) == 2:
                # Formato: action_cluster
                action, cluster_name = parts
                
                if action == "metricas":
                    context.args = [cluster_name]
                    await self.metricas_command(update, context)
                elif action == "operadores":
                    context.args = [cluster_name]
                    await self.operadores_command(update, context)
                elif action == "operators":
                    context.args = [cluster_name]
                    await self.operadores_command(update, context)
                elif action == "nodes":
                    context.args = [cluster_name]
                    await self.nodes_command(update, context)
                elif action == "namespaces":
                    context.args = [cluster_name]
                    await self.namespaces_command(update, context)
                elif action == "pods":
                    # Para pods necesitamos mostrar namespaces primero
                    await self.show_namespace_selection(update, context, cluster_name)
                elif action == "actualizar":
                    await query.edit_message_text("🔄 Actualizando datos...")
                    # Aquí podrías forzar una actualización del monitor
                    # Por ahora solo mostramos el mensaje
                    await query.edit_message_text("✅ Datos actualizados. Usa /status para ver el estado actual.")
            
            elif len(parts) == 3:
                # Formato: pods_cluster_namespace
                action, cluster_name, namespace_name = parts
                
                if action == "pods":
                    context.args = [cluster_name, namespace_name]
                    await self.pods_command(update, context)
    
    async def show_cluster_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
        """Mostrar selección de cluster para una acción específica"""
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay clusters disponibles.")
            return
        
        clusters = list(self.monitor.cluster_statuses.keys())
        
        # Crear botones para cada cluster con callback_data único
        keyboard = []
        for cluster in clusters:
            # Generar callback_data único
            callback_id = self._generate_callback_id(action, cluster)
            keyboard.append([InlineKeyboardButton(f"🏠 {cluster}", callback_data=callback_id)])
        
        # Botón para volver al menú
        keyboard.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        action_names = {
            "operators": "Operadores",
            "nodes": "Nodos",
            "namespaces": "Namespaces",
            "pods": "Pods"
        }
        
        message_text = f"""
🏠 **Selecciona un Cluster**

Para ver **{action_names.get(action, action)}**, selecciona un cluster:

{chr(10).join([f"• {cluster}" for cluster in clusters])}

🔙 **Para volver:** Usa el botón "Volver al Menú"
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_help_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostrar menú de ayuda detallado"""
        help_text = """
❓ **AYUDA - Monitor OpenShift**

📋 **Comandos disponibles:**
• `/menu` - Mostrar menú interactivo
• `/status` - Estado general del cluster
• `/report` - Generar reporte completo en /reports
• `/operators` - Estado de operadores
• `/nodes` - Estado de nodos
• `/namespaces` - Lista de namespaces
• `/namespace <cluster> <nombre>` - Estado de namespace específico
• `/pods <cluster> <namespace>` - Lista de pods en namespace

💡 **Tips:**
• Usa `/menu` para acceso rápido
• Los reportes se guardan en `/reports`
• Las alertas se envían automáticamente
• Puedes usar comandos o botones del menú

🔄 **Para volver al menú:** Usa el botón "Volver al Menú"
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=help_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text=help_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def handle_refresh_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar acción de refrescar"""
        await update.callback_query.edit_message_text(
            text="🔄 **Refrescando datos...**\n\n⏳ Obteniendo información actualizada...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Simular refresco
        await asyncio.sleep(1)
        
        await update.callback_query.edit_message_text(
            text="✅ **Datos actualizados**\n\n🕐 Última actualización: " + 
                 datetime.now().strftime('%H:%M:%S'),
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Volver al menú después de 2 segundos
        await asyncio.sleep(2)
        await self.show_menu(update, context)
    
    async def namespaces_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /namespaces - Estado de todos los namespaces de un cluster"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        cluster_name = context.args[0] if context.args else list(self.monitor.cluster_statuses.keys())[0]
        
        if cluster_name not in self.monitor.cluster_statuses:
            available_clusters = ", ".join(self.monitor.cluster_statuses.keys())
            await self.send_response(update, f"❌ Cluster no encontrado. Disponibles: {available_clusters}")
            return
        
        status = self.monitor.cluster_statuses[cluster_name]
        
        if not status.namespaces_status:
            await self.send_response(update, f"⚠️ No hay información de namespaces disponible para {cluster_name}")
            return
        
        # Crear tabla de namespaces
        namespaces_message = f"📁 **Namespaces en {cluster_name}**\n\n"
        namespaces_message += "| Namespace | Pods | Running | Failed | Pending | Services | Deployments |\n"
        namespaces_message += "|-----------|------|---------|--------|---------|----------|-------------|\n"
        
        for namespace_name, namespace_status in status.namespaces_status.items():
            if namespace_status.pods_count > 0:  # Solo mostrar namespaces con pods
                status_emoji = "🟢" if namespace_status.pods_failed == 0 else "🟡" if namespace_status.pods_pending > 0 else "🔴"
                namespaces_message += f"| {namespace_name} | {status_emoji} {namespace_status.pods_count} | {namespace_status.pods_running} | {namespace_status.pods_failed} | {namespace_status.pods_pending} | {namespace_status.services_count} | {namespace_status.deployments_count} |\n"
        
        # Agregar resumen
        total_namespaces = len([ns for ns in status.namespaces_status.values() if ns.pods_count > 0])
        total_pods = sum(ns.pods_count for ns in status.namespaces_status.values())
        failed_pods = sum(ns.pods_failed for ns in status.namespaces_status.values())
        
        namespaces_message += f"\n**📊 Resumen:**\n"
        namespaces_message += f"📁 Namespaces activos: {total_namespaces}\n"
        namespaces_message += f"🐳 Total de pods: {total_pods}\n"
        if failed_pods > 0:
            namespaces_message += f"🚨 Pods fallando: {failed_pods}\n"
        
        await self.send_response(update, namespaces_message, ParseMode.MARKDOWN)

    async def namespace_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /namespace - Estado de un namespace específico"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        if len(context.args) < 2:
            await self.send_response(update, "❌ Uso: /namespace [cluster] [nombre_namespace]")
            return
        
        cluster_name = context.args[0]
        namespace_name = context.args[1]
        
        if cluster_name not in self.monitor.cluster_statuses:
            available_clusters = ", ".join(self.monitor.cluster_statuses.keys())
            await self.send_response(update, f"❌ Cluster no encontrado. Disponibles: {available_clusters}")
            return
        
        status = self.monitor.cluster_statuses[cluster_name]
        
        if namespace_name not in status.namespaces_status:
            await self.send_response(update, f"❌ Namespace '{namespace_name}' no encontrado en {cluster_name}")
            return
        
        namespace_status = status.namespaces_status[namespace_name]
        
        # Crear mensaje detallado del namespace
        namespace_message = f"📁 **Namespace: {namespace_name}**\n"
        namespace_message += f"**🏠 Cluster:** {cluster_name}\n\n"
        
        # Estado general
        if namespace_status.pods_failed > 0:
            status_emoji = "🔴"
            status_text = "Crítico"
        elif namespace_status.pods_pending > 0:
            status_emoji = "🟡"
            status_text = "Advertencia"
        else:
            status_emoji = "🟢"
            status_text = "Saludable"
        
        namespace_message += f"**🏥 Estado:** {status_emoji} {status_text}\n\n"
        
        # Estadísticas de pods
        namespace_message += f"**🐳 Pods:**\n"
        namespace_message += f"• Total: {namespace_status.pods_count}\n"
        namespace_message += f"• Running: {namespace_status.pods_running} ✅\n"
        namespace_message += f"• Failed: {namespace_status.pods_failed} ❌\n"
        namespace_message += f"• Pending: {namespace_status.pods_pending} ⏳\n\n"
        
        # Otros recursos
        namespace_message += f"**🔧 Recursos:**\n"
        namespace_message += f"• Services: {namespace_status.services_count}\n"
        namespace_message += f"• Deployments: {namespace_status.deployments_count}\n\n"
        
        # Pods críticos si los hay
        if namespace_status.critical_pods:
            namespace_message += f"**🚨 Pods con Problemas:**\n"
            for pod in namespace_status.critical_pods:
                namespace_message += f"• {pod}\n"
        
        await self.send_response(update, namespace_message, ParseMode.MARKDOWN)

    async def pods_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /pods - Lista de pods en un namespace"""
        if not self.is_authorized(update):
            return
            
        if not self.monitor or not self.monitor.cluster_statuses:
            await self.send_response(update, "⚠️ No hay datos disponibles.")
            return
        
        if len(context.args) < 2:
            await self.send_response(update, "❌ Uso: /pods [cluster] [namespace]")
            return
        
        cluster_name = context.args[0]
        namespace_name = context.args[1]
        
        if cluster_name not in self.monitor.cluster_statuses:
            available_clusters = ", ".join(self.monitor.cluster_statuses.keys())
            await self.send_response(update, f"❌ Cluster no encontrado. Disponibles: {available_clusters}")
            return
        
        status = self.monitor.cluster_statuses[cluster_name]
        
        if namespace_name not in status.namespaces_status:
            await self.send_response(update, f"❌ Namespace '{namespace_name}' no encontrado en {cluster_name}")
            return
        
        namespace_status = status.namespaces_status[namespace_name]
        
        if namespace_status.pods_count == 0:
            await self.send_response(update, f"📁 El namespace '{namespace_name}' no tiene pods")
            return
        
        # Crear mensaje detallado de pods
        pods_message = f"🐳 **Pods en {namespace_name}**\n"
        pods_message += f"🏠 **Cluster:** {cluster_name}\n\n"
        
        # Resumen general
        pods_message += f"**📊 Resumen:**\n"
        pods_message += f"• Total: {namespace_status.pods_count}\n"
        pods_message += f"• Running: {namespace_status.pods_running} ✅\n"
        pods_message += f"• Failed: {namespace_status.pods_failed} ❌\n"
        pods_message += f"• Pending: {namespace_status.pods_pending} ⏳\n\n"
        
        # Obtener información detallada de pods usando la API
        try:
            # Usar el monitor para obtener detalles de pods
            cluster_config = None
            for cluster in self.monitor.clusters:
                if cluster.name == cluster_name:
                    cluster_config = cluster
                    break
            
            if cluster_config:
                # Obtener pods del namespace usando la API
                pods_result = self.monitor.execute_openshift_api_call(
                    cluster_config, 
                    f'/api/v1/namespaces/{namespace_name}/pods'
                )
                
                if pods_result['success']:
                    pods_data = pods_result['data']
                    
                    # Agrupar pods por estado
                    running_pods = []
                    failed_pods = []
                    pending_pods = []
                    other_pods = []
                    
                    for pod in pods_data.get('items', []):
                        pod_name = pod['metadata']['name']
                        status = pod['status']['phase']
                        ready = pod['status'].get('ready', False)
                        restart_count = 0
                        
                        # Obtener restart count si está disponible
                        if 'containerStatuses' in pod['status']:
                            for container in pod['status']['containerStatuses']:
                                restart_count = max(restart_count, container.get('restartCount', 0))
                        
                        # Crear información del pod
                        pod_info = f"• {pod_name}"
                        if restart_count > 0:
                            pod_info += f" (🔄 {restart_count} restarts)"
                        
                        # Agrupar por estado
                        if status == 'Running':
                            running_pods.append(pod_info)
                        elif status == 'Failed':
                            failed_pods.append(pod_info)
                        elif status == 'Pending':
                            pending_pods.append(pod_info)
                        else:
                            other_pods.append(pod_info)
                    
                    # Mostrar pods por estado
                    if running_pods:
                        pods_message += f"**✅ Pods Running ({len(running_pods)}):**\n"
                        pods_message += "\n".join(running_pods[:10])  # Mostrar máximo 10
                        if len(running_pods) > 10:
                            pods_message += f"\n... y {len(running_pods) - 10} más"
                        pods_message += "\n\n"
                    
                    if failed_pods:
                        pods_message += f"**❌ Pods Failed ({len(failed_pods)}):**\n"
                        pods_message += "\n".join(failed_pods[:5])  # Mostrar máximo 5 fallidos
                        if len(failed_pods) > 5:
                            pods_message += f"\n... y {len(failed_pods) - 5} más"
                        pods_message += "\n\n"
                    
                    if pending_pods:
                        pods_message += f"**⏳ Pods Pending ({len(pending_pods)}):**\n"
                        pods_message += "\n".join(pending_pods[:5])  # Mostrar máximo 5 pendientes
                        if len(pending_pods) > 5:
                            pods_message += f"\n... y {len(pending_pods) - 5} más"
                        pods_message += "\n\n"
                    
                    if other_pods:
                        pods_message += f"**❓ Otros Estados ({len(other_pods)}):**\n"
                        pods_message += "\n".join(other_pods[:3])  # Mostrar máximo 3 otros
                        if len(other_pods) > 3:
                            pods_message += f"\n... y {len(other_pods) - 3} más"
                        pods_message += "\n\n"
                    
                else:
                    pods_message += f"⚠️ No se pudieron obtener detalles de pods: {pods_result.get('error', 'Error desconocido')}\n"
            else:
                pods_message += f"⚠️ No se pudo obtener configuración del cluster\n"
                
        except Exception as e:
            pods_message += f"⚠️ Error obteniendo detalles de pods: {str(e)}\n"
        
        # Pods críticos si los hay
        if namespace_status.critical_pods:
            pods_message += f"**🚨 Pods con Problemas:**\n"
            for pod in namespace_status.critical_pods[:5]:  # Mostrar máximo 5 críticos
                pods_message += f"• {pod}\n"
            if len(namespace_status.critical_pods) > 5:
                pods_message += f"... y {len(namespace_status.critical_pods) - 5} más\n"
        
        await self.send_response(update, pods_message, ParseMode.MARKDOWN)
    
    def is_authorized(self, update: Update) -> bool:
        """Verificar si el usuario está autorizado - siempre True"""
        # No se requiere autorización - cualquier usuario puede usar el bot
        return True
    
    async def send_response(self, update: Update, message: str, parse_mode: str = ParseMode.MARKDOWN):
        """Enviar respuesta tanto para comandos como para botones inline"""
        try:
            if update.callback_query:
                # Es un botón inline, editar el mensaje
                await update.callback_query.edit_message_text(
                    text=message,
                    parse_mode=parse_mode
                )
            elif update.message:
                # Es un comando directo, responder al mensaje
                await update.message.reply_text(
                    text=message,
                    parse_mode=parse_mode
                )
            else:
                # Fallback: enviar mensaje al chat del callback query
                if update.callback_query:
                    await update.callback_query.message.reply_text(
                        text=message,
                        parse_mode=parse_mode
                    )
        except Exception as e:
            logger.error(f"Error enviando respuesta: {e}")
            # Fallback: intentar enviar mensaje nuevo
            try:
                if update.callback_query:
                    await update.callback_query.message.reply_text(message)
                elif update.message:
                    await update.message.reply_text(message)
            except Exception as e2:
                logger.error(f"Error en fallback de respuesta: {e2}")
    
    async def send_notification(self, message: str, parse_mode: str = ParseMode.MARKDOWN):
        """Enviar notificación a todos los chats registrados"""
        if not self.chat_ids:
            logger.warning("No hay chats registrados para enviar notificaciones")
            return
        
        for chat_id in self.chat_ids:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
                logger.info(f"Notificación enviada a chat {chat_id}")
            except Exception as e:
                logger.error(f"Error enviando notificación a chat {chat_id}: {e}")
    
    async def send_message_to_chat(self, chat_id: str, message: str, parse_mode: str = ParseMode.MARKDOWN):
        """Enviar mensaje a un chat específico"""
        try:
            # Convertir chat_id a int si es string
            if isinstance(chat_id, str):
                chat_id = int(chat_id)
            
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info(f"Mensaje enviado a chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error enviando mensaje a chat {chat_id}: {e}")
            return False
    
    async def send_cluster_status_notification(self, cluster_name: str, status):
        """Enviar notificación de estado de cluster"""
        health_emoji = {
            "HEALTHY": "🟢",
            "WARNING": "🟡", 
            "CRITICAL": "🔴",
            "ERROR": "❌"
        }
        health_icon = health_emoji.get(status.overall_health, "❓")
        
        # Solo enviar notificaciones para estados críticos o cambios importantes
        if status.overall_health in ["CRITICAL", "ERROR"]:
            message = f"""
🚨 **Alerta de Cluster: {cluster_name}**

Estado: {health_icon} {status.overall_health}
Hora: {status.timestamp.strftime('%H:%M:%S')}

**Problemas detectados:**
"""
            for issue in status.critical_issues[:3]:
                message += f"• {issue}\n"
            
            if len(status.critical_issues) > 3:
                message += f"... y {len(status.critical_issues) - 3} más"
            
            await self.send_notification(message)
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar mensajes de texto no comandos"""
        text = update.message.text.lower()
        
        if text in ['menu', 'menú', 'opciones', 'ayuda', 'help']:
            await self.show_menu(update, context)
        elif text in ['estado', 'status', 'cluster']:
            await self.status_command(update, context)
        elif text in ['reporte', 'report', 'informe']:
            await self.report_command(update, context)
        elif text in ['operadores', 'operators']:
            await self.operadores_command(update, context)
        elif text in ['nodos', 'nodes']:
            await self.nodes_command(update, context)
        elif text in ['namespaces', 'namespace']:
            await self.namespaces_command(update, context)
        elif text in ['pods', 'pod']:
            await self.namespaces_command(update, context)
        else:
            await update.message.reply_text(
                "🤖 No entiendo ese mensaje. Usa `/menu` para ver las opciones disponibles.",
                parse_mode='Markdown'
            )
    

    
    def setup_handlers(self):
        """Configurar manejadores de comandos"""
        # Comandos principales
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("ayuda", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("report", self.report_command))
        self.application.add_handler(CommandHandler("informe", self.informe_command))
        self.application.add_handler(CommandHandler("metricas", self.metricas_command))
        self.application.add_handler(CommandHandler("operadores", self.operadores_command))
        self.application.add_handler(CommandHandler("nodos", self.nodes_command))
        self.application.add_handler(CommandHandler("namespaces", self.namespaces_command))
        self.application.add_handler(CommandHandler("namespace", self.namespace_command))
        self.application.add_handler(CommandHandler("pods", self.pods_command))

        self.application.add_handler(CommandHandler("ping", self.ping_command))
        self.application.add_handler(CommandHandler("tiempo", self.tiempo_command))
        
        # Callbacks de botones
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Manejador para mensajes de texto
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Manejador de errores
        self.application.add_error_handler(self.error_handler)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Manejar errores del bot"""
        logger.error(f"Error en el bot: {context.error}")
        
        # Si es un error de BadRequest, intentar manejar específicamente
        if hasattr(context.error, '__class__') and 'BadRequest' in str(context.error.__class__):
            if 'Button_data_invalid' in str(context.error):
                logger.warning("Error de callback_data inválido, limpiando mapeo...")
                # Limpiar el mapeo de callbacks para evitar futuros errores
                self.callback_mapping.clear()
                self.callback_counter = 0
                
                # Intentar enviar mensaje de error al usuario
                try:
                    if update and hasattr(update, 'callback_query'):
                        await update.callback_query.answer("⚠️ Error en botones, por favor usa /menu para continuar")
                    elif update and hasattr(update, 'message'):
                        await update.message.reply_text("⚠️ Error en botones, por favor usa /menu para continuar")
                except Exception as e:
                    logger.error(f"No se pudo enviar mensaje de error: {e}")
            else:
                logger.error(f"Error de Telegram API: {context.error}")
        else:
            logger.error(f"Error general: {context.error}")
    
    async def start_bot(self):
        """Iniciar el bot"""
        try:
            self.application = Application.builder().token(self.token).build()
            self.setup_handlers()
            
            logger.info("Bot de Telegram iniciado correctamente")
            
            # Iniciar el bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot de Telegram ejecutándose")
            
        except Exception as e:
            logger.error(f"Error iniciando bot de Telegram: {e}")
            raise
    
    async def stop_bot(self):
        """Detener el bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot de Telegram detenido") 