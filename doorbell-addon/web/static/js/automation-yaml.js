// Pure YAML generator for the Trigger Helper. No DOM dependencies so it can be
// unit-tested in node (see automation-yaml.test.js).
//
// When a camera entity is configured, the generated automation snapshots that
// camera at the instant of the press and hands the file to WhoRang via
// image_path — WhoRang then uses that frame and skips its own (later) capture,
// eliminating the ring-to-capture delay. RTSP/URL users (no camera entity) get
// the simple version.
function buildAutomationYaml(triggerEntity, cameraEntity) {
    const restCommand = cameraEntity
        ? `rest_command:
  doorbell_ring:
    url: "http://localhost:8099/api/doorbell/ring"
    method: POST
    content_type: "application/x-www-form-urlencoded"
    payload: "image_path={{ image_path | default('') }}"`
        : `rest_command:
  doorbell_ring:
    url: "http://localhost:8099/api/doorbell/ring"
    method: POST`;

    const automation = cameraEntity
        ? `alias: Doorbell ring
triggers:
  - trigger: state
    entity_id: ${triggerEntity}
    from: "off"
    to: "on"
variables:
  snapshot_path: "/config/www/whorang_last_press.jpg"
actions:
  - action: camera.snapshot
    target:
      entity_id: ${cameraEntity}
    data:
      filename: "{{ snapshot_path }}"
  - action: rest_command.doorbell_ring
    data:
      image_path: "{{ snapshot_path }}"`
        : `alias: Doorbell ring
triggers:
  - trigger: state
    entity_id: ${triggerEntity}
    from: "off"
    to: "on"
actions:
  - action: rest_command.doorbell_ring`;

    return `# Add to configuration.yaml:
${restCommand}

# Automation:
${automation}`;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { buildAutomationYaml };
}
