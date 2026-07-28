{{- define "app-logs-metrics-engine.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "app-logs-metrics-engine.labels" -}}
helm.sh/chart: {{ include "app-logs-metrics-engine.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "app-logs-metrics-engine.instanceName" -}}
{{- printf "%s-%s" .Release.Name .app.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
