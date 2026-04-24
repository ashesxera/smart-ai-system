# Volcengine Ark 3D Generation API Specification

## 1. Global Configuration
- **Base URL**: `https://ark.cn-beijing.volces.com/api/v3`
- **Authentication**: `Authorization: Bearer {API_KEY}`
- **Content-Type**: `application/json`
- **Task Nature**: Asynchronous (Create $\rightarrow$ Poll $\rightarrow$ Result)
- **Asset TTL**: 24 Hours

## 2. Endpoints Mapping

### 2.1 Task Management
| Action | Method | Path | Description |
| :--- | :--- | :--- | :--- |
| Create Task | `POST` | `/contents/generations/tasks` | Init 3D generation task |
| Get Task | `GET` | `/contents/generations/tasks/{id}` | Query task status and result |
| List Tasks | `GET` | `/contents/generations/tasks` | Filter and list history (last 7 days) |
| Delete Task | `DELETE` | `/contents/generations/tasks/{id}` | Cancel queued or delete finished records |

---

## 3. Model-Specific Schemas

### 3.1 Seed3D (`doubao-seed3d`)
- **Capabilities**: Image-to-3D
- **Request Body**:
  - `model`: `string` (Required)
  - `content`: `array` (Required)
    - `type`: `"image_url"` or `"text"`
    - `image_url`: `{ "url": "string" }` (URL or Base64)
    - `text`: `string` (Commands: `--subdivisionlevel {low|medium|high}`, `--fileformat {glb|obj|usd|usdz}`)
- **Defaults**: `fileformat: glb`, `subdivisionlevel: medium`

### 3.2 影眸 (`YingMou`)
- **Capabilities**: Image-to-3D (1-5 images), Text-to-3D, Hybrid
- **Request Body**:
  - `model`: `string` (Required)
  - `content`: `array` (Required)
    - `type`: `"image_url"` or `"text"`
    - `image_url`: `{ "url": "string" }`
    - `text`: `string` (Prompt + commands)
  - `seed`: `integer` [0, 65535]
  - `callback_url`: `string` (Optional)
- **Text Command Parameters**:
  - `--material`: `{PBR|Shaded|All}` (Default: `PBR`)
  - `--mesh_mode`: `{Raw|Quad}` (Default: `Quad`)
  - `--quality_override`: `number` (Raw: [500, 1M], Quad: [1k, 200k])
  - `--use_original_alpha`: `boolean` (Preserve transparency)
  - `--bbox_condition`: `integer[3]` (e.g., `[100,100,100]`)
  - `--addons`: `{HighPack}` (Enable 4K textures)
  - `--subdivisionlevel`: `{high|medium|low}`
  - `--fileformat`: `{glb|obj|usdz|fbx|stl}` (Default: `glb`)
  - `--hd_texture`: `boolean`
  - `--TAPose`: `boolean` (Force T/A Pose for humanoid)

### 3.3 数美 (`Shumei`)
- **Capabilities**: Image-to-3D (1-4 images), Text-to-3D
- **Request Body**:
  - `model`: `string` (Required)
  - `content`: `array` (Required)
  - `multi_images_bit`: `string` (View map: 1=present, 0=absent. Order: Front, Back, Left, Right)
- **Text Command Parameters**:
  - `--resolution`: `{1536|1536pro}` (Default: `1536`)
  - `--request_type`: `integer` (1: Geometry Only, 3: Geometry + Texture)
  - `--ff` (fileformat): `integer` (1:obj, 2:glb, 3:stl, 4:fbx, 5:usdz)
  - `--face`: `integer` [100k, 2M] (Polygon count)

---

## 4. State Machine & Response

### 4.1 Task Status (`status`)
- `queued`: Waiting in line. (Deletable $\rightarrow$ `cancelled`)
- `running`: Processing. (Non-deletable)
- `succeeded`: Finished. (Deletable $\rightarrow$ Record removed)
- `failed`: Error occurred. (Deletable $\rightarrow$ Record removed)
- `cancelled`: Cancelled. (Auto-deleted after 24h)

### 4.2 Response Structure (Get Task)
```json
{
  "id": "string",
  "model": "string",
  "status": "string",
  "content": {
    "file_url": "string" // Only present when status == 'succeeded'
  },
  "usage": {
    "completion_tokens": "integer",
    "total_tokens": "integer"
  },
  "error": {
    "code": "string",
    "message": "string"
  },
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## 5. Constraints & Validation
- **Image Size**: $\le 10\text{MB}$ (Seed3D/Shumei), $\le 30\text{MB}$ (YingMou)
- **Image Resolution**: $\le 4096 \times 4096\text{px}$
- **Image Formats**: `jpg, jpeg, png, webp, bmp`
- **Text Prompt**: English only, $\le 400$ characters.
