package urp

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestWorkUnitBinaryEnvelope(t *testing.T) {
	workUnit, err := ByteObjectWorkUnit("acme", "s3://bucket/key", []byte{0, 1, 255}).Build()
	if err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(workUnit)
	if err != nil {
		t.Fatal(err)
	}
	var document map[string]any
	if err := json.Unmarshal(encoded, &document); err != nil {
		t.Fatal(err)
	}
	payload := document["payload"].(map[string]any)
	if payload["_urp_encoding"] != "base64" || payload["data"] != "AAH/" {
		t.Fatalf("unexpected payload envelope: %#v", payload)
	}
	var restored WorkUnit
	if err := json.Unmarshal(encoded, &restored); err != nil {
		t.Fatal(err)
	}
	if string(restored.Payload.([]byte)) != string([]byte{0, 1, 255}) {
		t.Fatalf("binary payload did not round trip: %#v", restored.Payload)
	}
}

func TestWorkUnitRejectsMalformedBinaryEnvelope(t *testing.T) {
	var workUnit WorkUnit
	err := json.Unmarshal(
		[]byte(`{"kind":"byte_object","tenant":"acme","logical_ref":"s3://bucket/key","payload":{"_urp_encoding":"base64","data":"%%%"}}`),
		&workUnit,
	)
	if err == nil {
		t.Fatal("expected malformed base64 envelope to fail")
	}
}

func TestClientAuthAndBinaryResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.Header.Get("authorization") != "Bearer secret" {
			t.Fatalf("missing authorization header")
		}
		if request.Header.Get("x-urp-tenant") != "acme" {
			t.Fatalf("missing tenant header")
		}
		_, _ = io.ReadAll(request.Body)
		writer.Header().Set("content-type", "application/octet-stream")
		_, _ = writer.Write([]byte{4, 5, 6})
	}))
	defer server.Close()

	client := NewAuthenticatedClient(server.URL, "secret", "acme")
	result, err := client.S3GetObject(context.Background(), S3ObjectByManifestRequest{ManifestID: "mf_test"})
	if err != nil {
		t.Fatal(err)
	}
	if string(result) != string([]byte{4, 5, 6}) {
		t.Fatalf("unexpected binary response: %v", result)
	}
}
