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
alias: Smart Doorbell Notification with AI (Example)
description: >-
  Example automation: Send notification with AI-generated message and show live 
  feed when doorbell is pressed. Replace all placeholder entities with your own devices.
triggers:
  - entity_id: binary_sensor.your_doorbell_button  # Replace with your doorbell button sensor
    from: "off"
    to: "on"
    trigger: state
actions:
  # Take a snapshot from the doorbell camera
  - target:
      entity_id: camera.your_doorbell_camera  # Replace with your doorbell camera entity
    data:
      filename: "{{ snapshot_path }}"
    action: camera.snapshot
  
  # Optional: Play doorbell sound on media players
  - target:
      entity_id:
        - media_player.living_room_speaker  # Replace with your media player entities
        - media_player.kitchen_speaker
    data:
      media:
        media_content_id: /local/sounds/doorbell.mp3  # Path to your doorbell sound file
        media_content_type: music
        metadata: {}
    action: media_player.play_media
    enabled: true
  
  # Analyze the snapshot with AI to generate description
  - data:
      remember: false
      use_memory: false
      include_filename: false
      target_width: 1280
      max_tokens: 100
      temperature: 0.2
      generate_title: true
      expose_images: true
      provider: YOUR_PROVIDER_ID  # Replace with your LLM Vision provider ID
      message: >-
        You are my sarcastic funny security guard. Describe what you see. Don't
        mention trees, bushes, grass, landscape, driveway, light fixtures, yard,
        brick, wall, garden. Don't mention the time and date. Be precise and
        short in one funny one liner of max 10 words. Only describe the person,
        vehicle or the animal.
      image_file: "{{ snapshot_path }}"
      model: gpt-4o-mini  # Or your preferred vision model
    response_variable: ai_description
    action: llmvision.image_analyzer
  
  # Send notifications and display video in parallel
  - parallel:
      # Notification to first mobile device
      - action: notify.mobile_app_your_phone  # Replace with your mobile app notify service
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
                uri: /dashboard-home/cameras  # Replace with your camera dashboard path
              - action: DISMISS
                title: ❌ Dismiss
      
      # Notification to second mobile device (optional)
      - action: notify.mobile_app_second_phone  # Replace or remove if not needed
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
                title: ❌ Dismiss
        enabled: true
      
      # Optional: Call REST command for external integration
      - action: rest_command.doorbell_notification  # Replace with your REST command if needed
        data:
          ai_message: "{{ ai_description.response_text }}"
          ai_title: "{{ ai_description.title }}"
          image_path: "{{ snapshot_path }}"
          image_url: "{{ snapshot_url }}"
        enabled: false  # Disabled by default, enable if you use this
      
      # Announce on smart display in kitchen
      - data:
          media_player_entity_id: media_player.kitchen_display  # Replace with your display
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com  # Replace with your TTS service
        enabled: true
      
      # Announce on smart display in office
      - data:
          media_player_entity_id: media_player.office_display  # Replace with your display
          message: "{{ ai_description.response_text }}"
          cache: true
        action: tts.speak
        target:
          entity_id: tts.google_translate_en_com  # Replace with your TTS service
        enabled: true
  
  # Stream live camera feed to Google Nest Hubs or smart displays
  - action: camera.play_stream
    target:
      entity_id: camera.your_doorbell_camera  # Replace with your doorbell camera entity
    data:
      media_player:
        - media_player.kitchen_display  # Replace with your smart display entities
        - media_player.office_display
      format: hls  # Use 'hls' for most devices, 'dash' as alternative
  
  # Wait before stopping the stream
  - delay:
      seconds: 20  # Adjust duration as needed
  
  # Stop the video stream on displays
  - target:
      entity_id:
        - media_player.kitchen_display  # Match the displays from camera.play_stream
        - media_player.office_display
    action: media_player.media_stop
    data: {}
    enabled: true

# Variables for file paths and URLs
variables:
  timestamp: "{{ now().timestamp() | int }}"
  snapshot_path: /config/www/doorbell_snapshot_{{ timestamp }}.jpg
  snapshot_url: https://your-ha-instance.com/local/doorbell_snapshot_{{ timestamp }}.jpg  # Replace with your Home Assistant URL
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
