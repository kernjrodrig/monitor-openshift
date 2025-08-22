# 🚀 OpenShift Monitor - Versión Simplificada

Sistema de monitoreo continuo para clusters OpenShift 4 con notificaciones por Telegram.

## ✨ Características

- 📊 **Monitoreo Continuo**: Revisa el estado del cluster cada 5 minutos
- 🚨 **Alertas Inteligentes**: Detecta problemas críticos automáticamente
- 📝 **Reportes Automáticos**: Genera reportes en Markdown cada hora
- 🤖 **Bot de Telegram**: Recibe notificaciones y comandos interactivos
- 🐳 **Contenedorizado**: Funciona con Docker y Podman
- 🔄 **Multi-Cluster**: Soporta múltiples clusters OpenShift

## 🚀 Inicio Rápido

### 1. Configurar el Monitor

```bash
# Copiar archivo de configuración
cp config.env.example config.env

# Editar configuración
nano config.env
```

### 2. Configurar Variables Críticas

```bash
# En config.env, actualiza estas variables:

# Tu token de OpenShift (obtener con: oc whoami -t)
OPENSHIFT_TOKENS=sha256~TU_TOKEN_REAL_AQUI

# URL de Prometheus de tu cluster
PROMETHEUS_URLS=https://prometheus-k8s-openshift-monitoring.apps.tu-cluster.com

# URL de Alertmanager de tu cluster
ALERTMANAGER_URLS=https://alertmanager-main-openshift-monitoring.apps.tu-cluster.com

# Nombre de tu cluster
CLUSTER_NAMES=mi-cluster-produccion

# Tu ID de usuario de Telegram
TELEGRAM_AUTHORIZED_USERS=TU_ID_DE_TELEGRAM
```

### 3. Levantar el Monitor

```bash
# Iniciar monitor
./start.sh start

# Ver estado
./start.sh status

# Ver logs
./start.sh logs
```

## 📋 Comandos Disponibles

| Comando | Descripción |
|---------|-------------|
| `./start.sh start` | Iniciar el monitor |
| `./start.sh stop` | Detener el monitor |
| `./start.sh restart` | Reiniciar el monitor |
| `./start.sh status` | Ver estado del monitor |
| `./start.sh logs` | Ver logs en tiempo real |
| `./start.sh config` | Ver configuración actual |
| `./start.sh help` | Mostrar ayuda |

## 🤖 Bot de Telegram

### 🚀 **Cómo Funciona el Bot**

El bot de Telegram proporciona una interfaz interactiva y fácil de usar para monitorear tu cluster OpenShift desde cualquier lugar. Funciona de dos maneras:

1. **Comandos directos** - Usando comandos como `/status`, `/report`, etc.
2. **Menú interactivo** - Usando botones inline para navegación fácil

### 📋 **Comandos Disponibles**

#### 🎯 **Comandos Principales (RECOMENDADOS)**
- `/menu` - **Menú interactivo con botones** - La forma más fácil de usar el bot
- `/start` - Iniciar el bot y mostrar bienvenida
- `/status` - Estado general de todos los clusters
- `/report [cluster]` - Generar reporte completo y guardarlo en `/reports`

#### 📁 **Monitoreo Detallado**
- `/operators [cluster]` - Estado de operadores del cluster
- `/nodes [cluster]` - Estado de nodos del cluster
- `/namespaces [cluster]` - Estado de todos los namespaces
- `/namespace [cluster] [nombre]` - Estado de un namespace específico
- `/pods [cluster] [namespace]` - Lista de pods en un namespace
- `/metricas [cluster]` - Métricas de CPU, memoria y disco

#### 🆘 **Utilidades**
- `/ayuda` - Mostrar ayuda (redirige a `/menu`)
- `/ping` - Verificar conectividad del bot
- `/tiempo` - Última verificación de cada cluster

### 🎮 **Menú Interactivo con Botones**

El comando `/menu` muestra un menú interactivo con botones que te permiten:

```
🎯 MENÚ PRINCIPAL - Monitor OpenShift

[📊 Estado General] [📋 Generar Reporte]
[⚙️ Operadores]    [🖥️ Nodos]
[📁 Namespaces]    [🐳 Pods]
[❓ Ayuda]         [🔄 Actualizar]
```

**Ventajas del menú:**
- ✅ **Navegación fácil** - No necesitas recordar comandos
- ✅ **Selección de cluster** - Elige el cluster antes de la acción
- ✅ **Botones de retorno** - Fácil navegación entre menús
- ✅ **Acceso rápido** - Todas las opciones en un lugar

### 📋 **Generación de Reportes a Petición**

#### 🆕 **Nuevo Sistema de Reportes**
- **Comando:** `/report [cluster]` o botón "📋 Generar Reporte"
- **Ubicación:** Los reportes se guardan en el directorio `/reports`
- **Formato:** Archivos Markdown con timestamp
- **Contenido:** Estado completo del cluster, operadores, nodos, namespaces y pods

#### 📁 **Estructura de Reportes**
```
reports/
├── cluster-4vscj-1_20250821_143022.md
├── cluster-4vscj-1_20250821_144522.md
└── cluster-4vscj-1_20250821_150022.md
```

#### 🎯 **Cuándo Generar Reportes**
- **Manual:** Cuando necesites un reporte específico
- **Auditoría:** Para documentar el estado del cluster
- **Análisis:** Para revisar problemas o cambios
- **Compartir:** Para enviar a otros equipos

### 🔧 **Configuración del Bot**

#### 📱 **Variables de Entorno**
```bash
# Token del bot de Telegram
TELEGRAM_BOT_TOKEN=tu_token_aqui

# Chat ID específico para notificaciones
TELEGRAM_CHAT_ID=814045254

# Sistema de alertas inteligentes
TELEGRAM_SMART_ALERTS=true
TELEGRAM_RECOVERY_NOTIFICATIONS=true
```

#### 🚀 **Iniciar el Bot**
```bash
# El bot se inicia automáticamente con el monitor
./start.sh start

# Ver logs del bot
./start.sh logs | grep telegram
```

### 📱 **Ejemplos de Uso**

#### 🎯 **Uso del Menú Interactivo**
1. **Enviar `/menu`** al bot
2. **Seleccionar "📊 Estado General"** para ver estado
3. **Seleccionar "📋 Generar Reporte"** para crear reporte
4. **Elegir cluster** de la lista
5. **Usar botones de retorno** para navegar

#### 📋 **Generar Reporte Completo**
```bash
# Comando directo
/report cluster-4vscj-1

# O usar el menú
/menu → 📋 Generar Reporte → 🏠 cluster-4vscj-1
```

#### 🐳 **Ver Pods de un Namespace**
```bash
# Comando directo
/pods cluster-4vscj-1 openshift-monitoring

# O usar el menú
/menu → 🐳 Pods → 🏠 cluster-4vscj-1 → openshift-monitoring
```

### 🚨 **Notificaciones Automáticas**

#### 🎯 **Sistema de Alertas Inteligentes**
- **Alertas automáticas** solo para problemas nuevos
- **Notificaciones de recuperación** cuando se resuelven problemas
- **Cambios de estado** importantes
- **Sin spam** de resúmenes automáticos

#### 📱 **Tipos de Notificaciones**
```
🚨 ALERTA: Nuevos Problemas en cluster-4vscj-1
• Pod con problemas: grafana-abc123 (openshift-monitoring)
• Nodo control-plane-1 caído
🕐 Hora: 14:05:00

🎉 PROBLEMA RESUELTO en cluster-4vscj-1
• Pod recuperado: grafana-abc123 (openshift-monitoring)
🕐 Hora: 14:15:00
```

### 🔒 **Seguridad del Bot**

#### ✅ **Características de Seguridad**
- **Sin autorización requerida** - Funciona con cualquier usuario
- **Comandos seguros** - Solo lectura, no modifica el cluster
- **Logs de auditoría** - Registra todas las acciones
- **Rate limiting** - Previene spam de comandos

#### 🛡️ **Buenas Prácticas**
- **Mantén privado** el token del bot
- **Usa chat privado** para notificaciones sensibles
- **Revisa logs** regularmente
- **Actualiza** el bot cuando sea necesario

### 🎯 **Mejores Prácticas**

#### 🚀 **Para Usuarios Nuevos**
1. **Empieza con `/menu`** - Es la forma más fácil
2. **Usa botones** - Navegación más intuitiva
3. **Genera reportes** cuando los necesites
4. **Configura alertas** para notificaciones automáticas

#### 📊 **Para Monitoreo Continuo**
1. **Configura `/status`** para ver estado general
2. **Usa `/operators`** para ver operadores críticos
3. **Monitorea `/pods`** en namespaces importantes
4. **Genera reportes** periódicamente para auditoría

#### 🔧 **Para Administradores**
1. **Configura `TELEGRAM_CHAT_ID`** para notificaciones directas
2. **Habilita alertas inteligentes** para problemas nuevos
3. **Revisa logs** del bot regularmente
4. **Personaliza comandos** según necesidades del equipo

### 🔄 **Flujo de Trabajo del Bot**

```
Usuario envía /menu
         ↓
   [Menú Principal]
         ↓
   Selecciona acción
         ↓
   [Selección de Cluster]
         ↓
   Ejecuta comando
         ↓
   [Resultado con Botones]
         ↓
   Botones de retorno
         ↓
   [Menú Principal]
```

### 🧠 **Inteligencia del Bot**

#### 🎯 **Características Inteligentes**
- **Detección de cambios** - Solo alerta sobre problemas nuevos
- **Navegación contextual** - Botones adaptados a la acción
- **Selección de cluster** - Lista dinámica de clusters disponibles
- **Manejo de errores** - Mensajes claros y útiles

#### 🔄 **Adaptabilidad**
- **Interfaz responsive** - Funciona en móvil y desktop
- **Navegación intuitiva** - Botones claros y descriptivos
- **Retorno fácil** - Siempre puedes volver al menú principal
- **Comandos flexibles** - Funciona con texto y botones

### 🌐 **Integración con el Monitor**

#### 🔗 **Conexión Bidireccional**
- **Monitor → Bot:** Envía alertas automáticas
- **Bot → Monitor:** Solicita información en tiempo real
- **Sincronización:** Estado siempre actualizado
- **Logs compartidos:** Trazabilidad completa

#### 📊 **Datos en Tiempo Real**
- **Estado del cluster** - Siempre actualizado
- **Métricas de recursos** - CPU, memoria, disco
- **Estado de operadores** - Salud del sistema
- **Namespaces y pods** - Estado de aplicaciones

### 🔧 **Solución de Problemas del Bot**

#### ❌ **Problemas Comunes**

**Bot no responde:**
```bash
# Verificar que esté ejecutándose
./start.sh status

# Ver logs del bot
./start.sh logs | grep telegram

# Reiniciar si es necesario
./start.sh restart
```

**Comandos no funcionan:**
```bash
# Verificar token
echo $TELEGRAM_BOT_TOKEN

# Verificar permisos
ls -la telegram_bot.py

# Reiniciar bot
./start.sh restart
```

**Menú no se muestra:**
```bash
# Usar comando directo
/menu

# Verificar logs de errores
./start.sh logs | grep -i error
```

#### ✅ **Solución de Errores**
1. **Revisar logs** - Identificar el problema específico
2. **Verificar configuración** - Token y variables de entorno
3. **Reiniciar servicios** - Bot y monitor
4. **Verificar conectividad** - Internet y API de Telegram

### 🚀 **Comandos Avanzados del Bot**

#### 🎯 **Comandos de Navegación**
```bash
# Menú principal
/menu

# Ayuda detallada
/ayuda

# Estado general
/status
```

#### 📋 **Comandos de Reportes**
```bash
# Generar reporte completo
/report cluster-4vscj-1

# Ver estado de operadores
/operators cluster-4vscj-1

# Ver métricas de recursos
/metricas cluster-4vscj-1
```

#### 🐳 **Comandos de Monitoreo**
```bash
# Ver namespaces
/namespaces cluster-4vscj-1

# Ver pods específicos
/pods cluster-4vscj-1 openshift-monitoring

# Ver nodos
/nodos cluster-4vscj-1
```

---

## 🎉 **¡Tu Bot de Telegram está Listo!**

Con estas mejoras, ahora tienes:
- ✅ **Menú interactivo** con botones fáciles de usar
- ✅ **Generación de reportes** a petición (no automática)
- ✅ **Navegación intuitiva** entre opciones
- ✅ **Comandos `/menu`** en lugar de `/ayuda`
- ✅ **Sistema de alertas inteligentes** para problemas nuevos
- ✅ **Interfaz moderna** y responsive

**Para empezar a usar:**
1. **Reinicia el monitor:** `./start.sh restart`
2. **Envía `/menu`** a tu bot en Telegram
3. **Explora las opciones** usando los botones
4. **Genera reportes** cuando los necesites

¡Disfruta de tu nuevo bot inteligente! 🚀 