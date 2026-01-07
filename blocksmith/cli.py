"""
BlockSmith CLI - Command-line interface for generating block models
"""

import click
import sys
from pathlib import Path
from blocksmith.client import Blocksmith
from blocksmith.converters.convert import convert as convert_model
from blocksmith.llm.exceptions import LLMAPIError, LLMServiceError, LLMTimeoutError


@click.group()
@click.version_option()
def cli():
    """
    BlockSmith - Generate voxel/block models from text using AI.

    Examples:
        blocksmith generate "a castle" -o castle.glb
        blocksmith convert model.glb model.bbmodel
    """
    pass


@cli.command()
@click.argument('prompt')
@click.option('-o', '--output', required=True, help='Output file path (.glb, .gltf, .bbmodel, .json, .py)')
@click.option('--model', default=None, help='LLM model to use (default: gemini/gemini-2.5-pro)')
@click.option('--image', default=None, help='Reference image (local file or URL)')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed generation statistics')
def generate(prompt, output, model, image, verbose):
    """
    Generate a block model from a text prompt.

    Examples:
        blocksmith generate "a medieval castle" -o castle.glb
        blocksmith generate "a tree" -o tree.bbmodel --model gemini/gemini-2.0-flash-exp
        blocksmith generate "blocky car" -o car.glb --image photo.jpg --verbose
    """
    try:
        # Initialize client
        bs = Blocksmith(default_model=model) if model else Blocksmith()

        # Show what we're doing
        click.echo(f"Generating: {prompt}")
        if image:
            click.echo(f"Using image: {image}")
        if verbose:
            click.echo(f"Model: {bs.default_model}")

        # Generate model (synchronous API call - no progress to track)
        result = bs.generate(prompt, image=image)

        # Save output
        click.echo(f"Saving to: {output}")
        result.save(output)

        # Show stats if verbose
        if verbose:
            click.echo("\nGeneration Statistics:")
            click.echo(f"  Tokens: {result.tokens.total_tokens} (prompt: {result.tokens.prompt_tokens}, completion: {result.tokens.completion_tokens})")
            if result.cost is not None:
                click.echo(f"  Cost: ${result.cost:.4f}")
            click.echo(f"  Model: {result.model}")
            click.echo(f"  DSL size: {len(result.dsl)} characters")

        click.secho(f"✓ Success! Model saved to {output}", fg='green')

    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)
    except LLMAPIError as e:
        click.secho(f"API Error: {e}", fg='red', err=True)
        sys.exit(1)
    except LLMServiceError as e:
        click.secho(f"Service Error: {e}", fg='red', err=True)
        sys.exit(1)
    except LLMTimeoutError as e:
        click.secho(f"Timeout Error: {e}", fg='red', err=True)
        sys.exit(1)
    except ValueError as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Unexpected error: {e}", fg='red', err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

@cli.command()
@click.argument("prompt")
@click.option("--model-file", "-m", required=True, type=click.Path(exists=True), help="Path to existing model Python file")
@click.option("--output", "-o", default="anim.py", help="Output file path (default: anim.py)")
@click.option("--model", help="LLM model override")
@click.option('--verbose', '-v', is_flag=True, help='Show detailed statistics')
def animate(prompt, model_file, output, model, verbose):
    """
    Generate animations for an existing model.
    
    Examples:
        blocksmith animate "walk cycle" -m steve.py -o walk.py
        blocksmith animate "wave hand" -m robot.py -o wave.py
    """
    try:
        # Initialize client
        bs = Blocksmith(default_model=model) if model else Blocksmith()

        if verbose:
            click.echo(f"Animating: {prompt}")
            click.echo(f"Base Model: {model_file}")

        # Read model code
        with open(model_file, 'r') as f:
            model_code = f.read()

        # Generate animation
        result = bs.animate(prompt, model_code, model=model)

        # Save output
        click.echo(f"Saving animation to: {output}")
        # Force saving as python file
        if not output.endswith('.py'):
            output += '.py'
        
        with open(output, 'w') as f:
            f.write(result.dsl)

        # Show stats if verbose
        if verbose:
            click.echo("\nGeneration Statistics:")
            click.echo(f"  Tokens: {result.tokens.total_tokens}")
            if result.cost is not None:
                click.echo(f"  Cost: ${result.cost:.4f}")
            click.echo(f"  Model: {result.model}")

        click.secho(f"✓ Success! Animation saved to {output}", fg='green')

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)



@cli.command()
@click.argument('input_path')
@click.argument('output_path')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed conversion info')
def convert(input_path, output_path, verbose):
    """
    Convert a model from one format to another.

    Supported formats: .glb, .gltf, .bbmodel, .json, .py

    Examples:
        blocksmith convert model.glb model.bbmodel
        blocksmith convert castle.json castle.py
    """
    try:
        # Check if input exists
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if verbose:
            click.echo(f"Converting: {input_path} → {output_path}")

        # Convert (synchronous operation - no progress to track)
        convert_model(input_path, output_path)

        click.secho(f"✓ Success! Converted to {output_path}", fg='green')

    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)
    except ValueError as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Unexpected error: {e}", fg='red', err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('-m', '--model', 'model_path', required=True, help='Path to the base model file (Python DSL).')
@click.option('-a', '--animation', 'anim_paths', multiple=True, help='Path to animation Python file(s). Can be specified multiple times.')
@click.option('-o', '--output', required=True, help='Output file path (.glb only supported for now).')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed linking info')
def link(model_path, anim_paths, output, verbose):
    """
    Link a base model with one or more animation files.
    
    This allows you to generate a static model first, generate animations separately,
    and then combine them into a single animated GLB file.
    
    Example:
        blocksmith link -m robot.py -a walk.py -a wave.py -o robot.glb
    """
    try:
        from blocksmith.converters.python.importer import import_python_from_file, import_animation_only
        from blocksmith.converters.gltf.exporter import export_glb

        # 1. Load Base Model
        if verbose:
            click.echo(f"Loading base model: {model_path}")
        
        if not Path(model_path).exists():
             raise FileNotFoundError(f"Model file not found: {model_path}")

        # We primarily support Python DSL for the linker as per design
        if not model_path.endswith('.py'):
             click.secho("Warning: Linker is designed for .py model files. Other formats might not work as expected.", fg='yellow')

        # Load model structure
        model_data = import_python_from_file(model_path)
        
        # Initialize animations list if missing
        if 'animations' not in model_data or model_data['animations'] is None:
            model_data['animations'] = []

        # 2. Load Animations
        for anim_path in anim_paths:
            if verbose:
                click.echo(f"Linking animation file: {anim_path}")
            
            if not Path(anim_path).exists():
                raise FileNotFoundError(f"Animation file not found: {anim_path}")
            
            with open(anim_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Extract animations using the helper
            anims = import_animation_only(code)
            
            if verbose:
                click.echo(f"  Found {len(anims)} animations: {[a['name'] for a in anims]}")
            
            model_data['animations'].extend(anims)

        # 3. Export
        if verbose:
            click.echo(f"Exporting combined model to: {output}")

        if output.endswith('.glb'):
            glb_bytes = export_glb(model_data)
            with open(output, 'wb') as f:
                f.write(glb_bytes)
        else:
             raise ValueError("Linker currently only supports .glb output.")

        click.secho(f"✓ Success! Linked model saved to {output}", fg='green')

    except Exception as e:
        click.secho(f"Error linking model: {e}", fg='red', err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == '__main__':
    main()
