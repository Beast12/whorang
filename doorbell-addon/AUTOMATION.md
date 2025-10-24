# Advanced Automation Examples

This document provides complete automation examples for integrating the WhoRang Doorbell Face Recognition addon with Home Assistant.

## Complete Automation with AI Descriptions

This automation includes:
- Camera snapshot capture
- Doorbell sound playback
- AI-generated descriptions (requires LLM Vision integration)
- Mobile notifications with action buttons
- TTS announcements
- Display integration
- Face recognition processing

```yaml
alias: Smart Doorbell Notification with AI
description: Send notification with AI-generated message when doorbell is pressed
triggers:
  - entity_id: binary_sensor.your_doorbell_button
    from: "off"
    to: "on"
    trigger: state
actions:
  # 1. Capture snapshot from doorbell camera
  - target:
      entity_id: camera.your_doorbell_camera
    data:
      filename: "{{ snapshot_path }}"
    action: camera.snapshot
  
  # 2. Play doorbell sound on speakers (optional)
  - target:
      device_id:
        - device_id_speaker_1
        - device_id_speaker_2
        - device_id_speaker_3
    data:
      media:
        media_content_id: /local/sounds/doorbell.mp3
        media_content_type: music
        metadata: {}
    action: media_player.play_media
    enabled: true
  
  # 3. Generate AI description of who's at the door (requires LLM Vision integration)
  - data:
      remember: false
      use_memory: false
      include_filename: false
      target_width: 1280
      max_tokens: 100
      temperature: 0.2
      generate_title: true
      expose_images: true
      provider: your_llm_provider_id
      message: >-
        You are my sarcastic funny security guard. Describe what you see. Don't
        mention trees, bushes, grass, landscape, driveway, light fixtures, yard,
        brick, wall, garden. Don't mention the time and date. Be precise and
        short in one funny one liner of max 10 words. Only describe the person,
        vehicle or the animal.
      image_file: "{{ snapshot_path }}"
      model: gpt-4o-mini
    response_variable: ai_description
    action: llmvision.image_analyzer
  
  # 4. Send notifications and process face recognition in parallel
  - parallel:
      # Send mobile notification to first phone
      - action: notify.mobile_app_phone_1
        data:
          message: "{{ ai_description.response_text }}"
          title: "{{ ai_description.title }}"
          data:
            image: /local/doorbell_snapshot_{{ timestamp }}.jpg
            ttl: 0
            priority: high
            clickAction: "{{ snapshot_url }}"
            actions:
              - action: VIEW_PHOTO
                title: 📷 Photo
                uri: "{{ snapshot_url }}"
              - action: OPEN_CAMERA
                title: 📹 Live
                uri: /dashboard-home/cameras
              - action: DISMISS
                title: ❌ Close
      
      # Send mobile notification to second phone
      - action: notify.mobile_app_phone_2
        data:
          message: "{{ ai_description.response_text }}"
          title: "{{ ai_description.title }}"
          data:
            image: /local/doorbell_snapshot_{{ timestamp }}.jpg
            ttl: 0
            priority: high
            clickAction: "{{ snapshot_url }}"
            actions:
              - action: VIEW_PHOTO
                title: 📷 Photo
                uri: "{{ snapshot_url }}"
              - action: OPEN_CAMERA
                title: 📹 Live
                uri: /dashboard-home/cameras
              - action: DISMISS
                title: ❌ Close
        enabled: true
      
      # Send to face recognition addon
      - action: rest_command.doorbell_ring
        data:
          ai_message: "{{ ai_description.response_text }}"
          ai_title: "{{ ai_description.title }}"
          image_path: "{{ snapshot_path }}"
          image_url: "{{ snapshot_url }}"
      
      # Announce via TTS on display 1
      - data:
          media_player_entity_id: media_player.kitchen_display
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com
        enabled: true
      
      # Announce via TTS on display 2
      - data:
          media_player_entity_id: media_player.office_display
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com
        enabled: true
  
  # 5. Show snapshot on displays
  - target:
      device_id:
        - device_id_display_1
        - device_id_display_2
    data:
      media:
        media_content_id: "{{ snapshot_url }}"
        media_content_type: image/jpeg
        metadata: {}
    action: media_player.play_media
    enabled: true
  
  # 6. Wait 15 seconds then stop displaying
  - delay:
      seconds: 15
  
  # 7. Stop media playback on displays
  - target:
      device_id:
        - device_id_display_1
        - device_id_display_2
    action: media_player.media_stop
    data: {}
    enabled: true

variables:
  timestamp: "{{ now().timestamp() | int }}"
  snapshot_path: /config/www/doorbell_snapshot_{{ timestamp }}.jpg
  snapshot_url: https://your-home-assistant-url.com/local/doorbell_snapshot_{{ timestamp }}.jpg
```

## Automation Using Addon Events

This automation triggers when a known person is detected:

```yaml
alias: Welcome Home Notification
description: Send notification when known person arrives
triggers:
  - platform: event
    event_type: doorbell_known_person
actions:
  - service: notify.mobile_app
    data:
      message: "{{ trigger.event.data.person_name }} is at the door ({{ (trigger.event.data.confidence * 100) | round(0) }}% confidence)"
      title: "Welcome Home!"
      data:
        image: "{{ trigger.event.data.image_url }}"
```

## Automation for Unknown Faces

Alert when an unknown person is detected:

```yaml
alias: Unknown Person Alert
description: Send alert when unknown person detected
triggers:
  - platform: event
    event_type: doorbell_unknown_person
actions:
  - service: notify.mobile_app
    data:
      message: "Unknown person detected at the door"
      title: "⚠️ Security Alert"
      data:
        image: "{{ trigger.event.data.image_url }}"
        priority: high
        ttl: 0
        actions:
          - action: VIEW_EVENT
            title: "View in Gallery"
            uri: "/api/hassio_ingress/doorbell_face_recognition/gallery"
```

## Placeholder Reference

| Placeholder | Replace With | How to Find |
|-------------|--------------|-------------|
| `binary_sensor.your_doorbell_button` | Your doorbell button entity | Developer Tools → States → Search "doorbell" |
| `camera.your_doorbell_camera` | Your camera entity | Settings → Devices → Camera → Entities |
| `device_id_speaker_*` | Speaker device IDs | Settings → Devices → Device → Copy ID from URL |
| `device_id_display_*` | Display device IDs | Settings → Devices → Device → Copy ID from URL |
| `your_llm_provider_id` | LLM Vision provider ID | LLM Vision integration settings |
| `notify.mobile_app_phone_*` | Notification service | Developer Tools → Services → Search "notify" |
| `media_player.kitchen_display` | Media player entities | Developer Tools → States → Search "media_player" |
| `https://your-home-assistant-url.com` | Your HA external URL | Settings → System → Network → External URL |

## Tips for Best Results

1. **Test incrementally** - Start with the simple automation, then add features
2. **Check logs** - Monitor Home Assistant logs for errors
3. **Verify REST command** - Test the doorbell_ring endpoint manually
4. **Adjust timeouts** - Increase timeout if face recognition is slow
5. **Optimize AI prompts** - Customize the LLM Vision message for your needs
