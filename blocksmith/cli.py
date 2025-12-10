"""
BlockSmith CLI - Command-line interface for generating block models
"""

import click
import sys
from pathlib import Path
from blocksmith import Blocksmith
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


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == '__main__':
    main()
