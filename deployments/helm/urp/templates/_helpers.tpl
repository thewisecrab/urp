{{- define "urp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "urp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "urp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "urp.labels" -}}
helm.sh/chart: {{ include "urp.chart" . }}
{{ include "urp.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "urp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "urp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: {{ .Values.runtime.serviceName }}
{{- end }}

{{- define "urp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "urp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "urp.secretName" -}}
{{- if .Values.secrets.create }}
{{- include "urp.fullname" . }}
{{- else }}
{{- required "secrets.existingSecret is required when secrets.create=false" .Values.secrets.existingSecret }}
{{- end }}
{{- end }}

{{- define "urp.pvcName" -}}
{{- default (include "urp.fullname" .) .Values.persistence.existingClaim }}
{{- end }}
