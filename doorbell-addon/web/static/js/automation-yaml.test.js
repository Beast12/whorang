// Tests for buildAutomationYaml() — run with: node --test
const test = require('node:test');
const assert = require('node:assert');
const { buildAutomationYaml } = require('./automation-yaml');

test('without a camera entity, generates the simple rest_command (no snapshot)', () => {
    const yaml = buildAutomationYaml('binary_sensor.my_doorbell', '');
    assert.match(yaml, /entity_id: binary_sensor\.my_doorbell/);
    assert.match(yaml, /- action: rest_command\.doorbell_ring/);
    // No press-time snapshot machinery in the simple variant.
    assert.doesNotMatch(yaml, /camera\.snapshot/);
    assert.doesNotMatch(yaml, /image_path/);
    assert.doesNotMatch(yaml, /content_type/);
});

test('uses the provided add-on host in the rest_command URL', () => {
    const yaml = buildAutomationYaml('binary_sensor.x', '', 'a48cb117-whorang');
    assert.match(yaml, /url: "http:\/\/a48cb117-whorang:8099\/api\/doorbell\/ring"/);
    assert.doesNotMatch(yaml, /localhost/);
});

test('defaults host to localhost when omitted', () => {
    const yaml = buildAutomationYaml('binary_sensor.x', '');
    assert.match(yaml, /url: "http:\/\/localhost:8099\/api\/doorbell\/ring"/);
});

test('with a camera entity, generates the low-latency press-time handoff', () => {
    const yaml = buildAutomationYaml('binary_sensor.my_doorbell', 'camera.front_door');
    // Snapshot is taken from the configured camera at press-time...
    assert.match(yaml, /- action: camera\.snapshot/);
    assert.match(yaml, /entity_id: camera\.front_door/);
    assert.match(yaml, /filename: "\{\{ snapshot_path \}\}"/);
    // ...and handed to WhoRang via image_path.
    assert.match(yaml, /content_type: "application\/x-www-form-urlencoded"/);
    assert.match(yaml, /payload: "image_path=\{\{ image_path \| default\(''\) \}\}"/);
    assert.match(yaml, /image_path: "\{\{ snapshot_path \}\}"/);
    // Trigger entity still present.
    assert.match(yaml, /entity_id: binary_sensor\.my_doorbell/);
});
