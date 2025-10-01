from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import (Flask, abort, flash, redirect, render_template, request,
                   url_for)
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-me"  # simple default for demo purposes
    app.config["UPLOAD_FOLDER"] = Path(app.root_path) / "static" / "uploads"

    data_dir = Path(app.root_path) / "data" / "characters"
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config["DATA_DIR"] = data_dir
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)

    ATTRIBUTE_FIELDS = [
        ("strength", "Força"),
        ("dexterity", "Destreza"),
        ("constitution", "Constituição"),
        ("intelligence", "Inteligência"),
        ("wisdom", "Sabedoria"),
        ("charisma", "Carisma"),
    ]

    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    @app.template_filter("nl2br")
    def nl2br_filter(value: str | None) -> Markup:
        if not value:
            return Markup("")
        escaped_value = escape(value)
        return Markup("<br>".join(escaped_value.splitlines()))

    def load_character(character_id: str) -> Dict[str, Any]:
        path = data_dir / f"{character_id}.json"
        if not path.exists():
            abort(404, description="Personagem não encontrado")
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        data["id"] = character_id
        return data

    def load_characters() -> list[Dict[str, Any]]:
        characters: list[Dict[str, Any]] = []
        for file_path in data_dir.glob("*.json"):
            with file_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            data["id"] = file_path.stem
            characters.append(data)
        return sorted(characters, key=lambda item: item.get("name", "").lower())

    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    def handle_image_upload(character_id: str, previous_image: str | None = None) -> str | None:
        uploaded_file = request.files.get("image")
        if not uploaded_file or not uploaded_file.filename:
            return previous_image

        if not allowed_file(uploaded_file.filename):
            flash("Formato de imagem inválido. Use png, jpg, jpeg, gif ou webp.", "error")
            return previous_image

        filename = secure_filename(uploaded_file.filename)
        extension = filename.rsplit(".", 1)[1].lower()
        final_name = f"{character_id}.{extension}"
        destination = app.config["UPLOAD_FOLDER"] / final_name

        uploaded_file.save(destination)

        if previous_image and previous_image != f"uploads/{final_name}":
            old_path = app.config["UPLOAD_FOLDER"] / Path(previous_image).name
            if old_path.exists():
                old_path.unlink()

        return f"uploads/{final_name}"

    def extract_character_form(existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
        attributes: Dict[str, int] = {}
        for key, _label in ATTRIBUTE_FIELDS:
            raw_value = request.form.get(f"attr_{key}", "")
            try:
                attributes[key] = int(raw_value)
            except ValueError:
                attributes[key] = 0

        return {
            "name": request.form.get("name", "").strip(),
            "race": request.form.get("race", "").strip(),
            "character_class": request.form.get("character_class", "").strip(),
            "background": request.form.get("background", "").strip(),
            "level": request.form.get("level", "1").strip() or "1",
            "hit_points": request.form.get("hit_points", "").strip(),
            "armor_class": request.form.get("armor_class", "").strip(),
            "speed": request.form.get("speed", "").strip(),
            "attributes": attributes,
            "proficiencies": request.form.get("proficiencies", ""),
            "equipment": request.form.get("equipment", ""),
            "spells": request.form.get("spells", ""),
            "notes": request.form.get("notes", ""),
            "image": existing.get("image") if existing else None,
        }

    @app.route("/")
    def index() -> str:
        characters = load_characters()
        return render_template("index.html", characters=characters)

    @app.route("/characters/new")
    def new_character() -> str:
        blank_character = {
            "name": "",
            "race": "",
            "character_class": "",
            "background": "",
            "level": "1",
            "hit_points": "",
            "armor_class": "",
            "speed": "",
            "attributes": {key: 10 for key, _ in ATTRIBUTE_FIELDS},
            "proficiencies": "",
            "equipment": "",
            "spells": "",
            "notes": "",
            "image": None,
        }
        return render_template(
            "form.html",
            character=blank_character,
            attribute_fields=ATTRIBUTE_FIELDS,
            form_action=url_for("create_character"),
            submit_label="Criar personagem",
        )

    @app.route("/characters", methods=["POST"])
    def create_character() -> Any:
        character_id = uuid.uuid4().hex
        character = extract_character_form()

        if not character["name"]:
            flash("O nome do personagem é obrigatório.", "error")
            return redirect(url_for("new_character"))

        character["image"] = handle_image_upload(character_id)

        save_path = data_dir / f"{character_id}.json"
        with save_path.open("w", encoding="utf-8") as fp:
            json.dump(character, fp, ensure_ascii=False, indent=2)

        flash("Personagem criado com sucesso!", "success")
        return redirect(url_for("view_character", character_id=character_id))

    @app.route("/characters/<character_id>")
    def view_character(character_id: str) -> str:
        character = load_character(character_id)
        return render_template("view.html", character=character, attribute_fields=ATTRIBUTE_FIELDS)

    @app.route("/characters/<character_id>/edit")
    def edit_character(character_id: str) -> str:
        character = load_character(character_id)
        return render_template(
            "form.html",
            character=character,
            attribute_fields=ATTRIBUTE_FIELDS,
            form_action=url_for("update_character", character_id=character_id),
            submit_label="Salvar alterações",
        )

    @app.route("/characters/<character_id>", methods=["POST"])
    def update_character(character_id: str) -> Any:
        existing = load_character(character_id)
        character = extract_character_form(existing)

        if not character["name"]:
            flash("O nome do personagem é obrigatório.", "error")
            return redirect(url_for("edit_character", character_id=character_id))

        character["image"] = handle_image_upload(character_id, previous_image=existing.get("image"))

        save_path = data_dir / f"{character_id}.json"
        with save_path.open("w", encoding="utf-8") as fp:
            json.dump(character, fp, ensure_ascii=False, indent=2)

        flash("Personagem atualizado!", "success")
        return redirect(url_for("view_character", character_id=character_id))

    @app.route("/characters/<character_id>/delete", methods=["POST"])
    def delete_character(character_id: str) -> Any:
        character = load_character(character_id)
        path = data_dir / f"{character_id}.json"
        if path.exists():
            path.unlink()
        if character.get("image"):
            image_path = app.config["UPLOAD_FOLDER"] / Path(character["image"]).name
            if image_path.exists():
                image_path.unlink()
        flash("Personagem removido.", "info")
        return redirect(url_for("index"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
